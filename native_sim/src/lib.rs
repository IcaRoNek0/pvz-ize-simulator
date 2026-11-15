//! Rust-side foundation for the pvz-ize Simulator migration.
//!
//! This crate deliberately starts with input normalization and a deterministic
//! frame/state boundary.  The Python Simulator remains the fidelity reference
//! until each behavior is ported and covered by differential tests.

use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashSet;
use std::fmt;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Plant {
    pub id: String,
    #[serde(rename = "type")]
    pub kind: String,
    pub row: u8,
    pub col: u8,
    /// Occupied board columns.  Most plants occupy one cell; cob cannon
    /// preserves the two-cell footprint [col, col + 1].
    pub footprint: Vec<u8>,
    pub hp: i32,
    pub cooldown: u32,
    #[serde(default)]
    pub state_timer: u32,
    #[serde(default = "default_layer")]
    pub layer: String,
}

fn default_layer() -> String {
    "main".to_owned()
}

fn plant_default_layer(kind: &str) -> &'static str {
    match kind {
        "pumpkin" => "shell",
        "lily_pad" | "flower_pot" => "base",
        _ => "main",
    }
}

impl Plant {
    pub fn x(&self) -> f64 {
        40.0 + 80.0 * f64::from(self.col - 1)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Zombie {
    pub id: String,
    #[serde(rename = "type")]
    pub kind: String,
    pub row: u8,
    /// Exactly one of `col` and `x` is accepted in source input.  The
    /// normalized state always stores both the public column and pixel x.
    pub col: u8,
    pub x: f64,
    /// Internal fixed-point position/speed (1/1000 px). Omitted at the JSON boundary.
    #[serde(skip)]
    pub x_fp: i64,
    #[serde(skip)]
    pub speed_fp: i64,
    pub hp: i32,
    #[serde(default)]
    pub helmet_hp: i32,
    #[serde(default)]
    pub shield_hp: i32,
    pub speed: f64,
    #[serde(default)]
    pub age: u64,
    #[serde(default)]
    pub chilled: u32,
    #[serde(default)]
    pub headless: bool,
    #[serde(default)]
    pub hypnotized: bool,
    #[serde(default = "default_true")]
    pub tool: bool,
    #[serde(default)]
    pub underground: Option<bool>,
    #[serde(default)]
    pub status: UnitStatus,
}

fn default_true() -> bool {
    true
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum UnitStatus {
    Active,
    Dead,
    EnteredHouse,
    Exited,
}

impl Default for UnitStatus {
    fn default() -> Self {
        Self::Active
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Brain {
    pub row: u8,
    pub hp: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Scenario {
    pub version: u8,
    pub seed: i64,
    pub max_frames: u64,
    pub plants: Vec<Plant>,
    pub zombies: Vec<Zombie>,
    pub brains: Vec<Brain>,
    pub runs: u32,
    pub allow_stacking: bool,
    pub movement_mode: String,
    pub mode: String,
    pub rakes: Vec<GridObject>,
    pub ladders: Vec<GridObject>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GridObject {
    pub row: u8,
    pub col: u8,
}

#[derive(Debug)]
pub enum InputError {
    Json(serde_json::Error),
    Invalid(String),
}

impl fmt::Display for InputError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Json(e) => write!(f, "JSON: {e}"),
            Self::Invalid(e) => f.write_str(e),
        }
    }
}
impl std::error::Error for InputError {}
impl From<serde_json::Error> for InputError {
    fn from(e: serde_json::Error) -> Self {
        Self::Json(e)
    }
}

fn u64_field(v: Option<&Value>, default: u64, name: &str) -> Result<u64, InputError> {
    match v {
        None | Some(Value::Null) => Ok(default),
        Some(x) => x
            .as_u64()
            .ok_or_else(|| InputError::Invalid(format!("{name}: expected unsigned integer"))),
    }
}
fn i64_field(v: Option<&Value>, default: i64, name: &str) -> Result<i64, InputError> {
    match v {
        None | Some(Value::Null) => Ok(default),
        Some(x) => x
            .as_i64()
            .ok_or_else(|| InputError::Invalid(format!("{name}: expected signed integer"))),
    }
}
fn f64_field(v: Option<&Value>, default: f64, name: &str) -> Result<f64, InputError> {
    match v {
        None | Some(Value::Null) => Ok(default),
        Some(x) => x
            .as_f64()
            .ok_or_else(|| InputError::Invalid(format!("{name}: expected number"))),
    }
}
fn bool_field(v: Option<&Value>, default: bool, name: &str) -> Result<bool, InputError> {
    match v {
        None | Some(Value::Null) => Ok(default),
        Some(x) => x
            .as_bool()
            .ok_or_else(|| InputError::Invalid(format!("{name}: expected boolean"))),
    }
}
fn string_field(v: Option<&Value>, default: &str, name: &str) -> Result<String, InputError> {
    match v {
        None | Some(Value::Null) => Ok(default.to_owned()),
        Some(x) => x
            .as_str()
            .map(ToOwned::to_owned)
            .ok_or_else(|| InputError::Invalid(format!("{name}: expected string"))),
    }
}
fn plant_default_hp(kind: &str) -> i32 {
    match kind {
        "wallnut" => 4_000,
        "tallnut" => 8_000,
        "pumpkin" => 4_000,
        "spikerock" => 450,
        _ => 300,
    }
}

fn plant_default_cooldown(kind: &str) -> u64 {
    match kind {
        // Native COB cannon starts armed after a 500-tick wind-up.  The
        // simple slice only migrates this safe arming/reload counter; its
        // targeted lob and splash remain on the Python fallback.
        "cob_cannon" => 500,
        _ => 0,
    }
}

fn zombie_default_hp(kind: &str) -> i32 {
    match kind {
        "imp" => 70,
        "pole_vaulting" => 500,
        "zamboni" => 1_350,
        "balloon" => 270,
        "pogo" => 500,
        "ladder" => 500,
        _ => 270,
    }
}

fn zombie_default_helmet(kind: &str) -> i32 {
    match kind {
        "conehead" => 370,
        "buckethead" => 1100,
        "football" => 1400,
        "digger" => 100,
        _ => 0,
    }
}

fn zombie_default_shield(kind: &str) -> i32 {
    match kind {
        "screen_door" => 1100,
        "ladder" => 500,
        "newspaper" => 150,
        _ => 0,
    }
}

fn zombie_default_speed(kind: &str) -> f64 {
    match kind {
        "football" => 0.32,
        "imp" => 0.423,
        "pole_vaulting" => 0.32,
        "zamboni" => 0.25,
        "balloon" => 0.2,
        "pogo" => 0.45,
        "newspaper" => 0.09,
        "flag" => 0.22,
        _ => 0.143,
    }
}

fn spawn_offset(kind: &str) -> f64 {
    match kind {
        "bungee" => 0.0,
        "boss" => -40.0,
        _ => -30.0,
    }
}

fn row(v: Option<&Value>, name: &str) -> Result<u8, InputError> {
    let n = u64_field(v, 3, name)?;
    if !(1..=5).contains(&n) {
        return Err(InputError::Invalid(format!("{name}: expected 1..5")));
    }
    Ok(n as u8)
}
fn col(v: Option<&Value>, name: &str) -> Result<u8, InputError> {
    let n = u64_field(v, 1, name)?;
    if !(1..=9).contains(&n) {
        return Err(InputError::Invalid(format!("{name}: expected 1..9")));
    }
    Ok(n as u8)
}

/// Parse the public scenario format and normalize omitted fields.  This is
/// intentionally strict about identity/coordinates, while allowing the
/// simulator catalog to remain the validation authority during migration.
pub fn parse_scenario(input: &str) -> Result<Scenario, InputError> {
    let root: Value = serde_json::from_str(input)?;
    let obj = root
        .as_object()
        .ok_or_else(|| InputError::Invalid("scenario: expected object".into()))?;
    let version = u64_field(obj.get("version"), 2, "version")? as u8;
    if version != 1 && version != 2 {
        return Err(InputError::Invalid("version: expected 1 or 2".into()));
    }
    let seed = i64_field(obj.get("seed"), 0, "seed")?;
    let max_frames = u64_field(obj.get("max_frames"), 100_000, "max_frames")?;
    let runs = u64_field(obj.get("runs"), 1, "runs")? as u32;
    if runs == 0 {
        return Err(InputError::Invalid(
            "runs: expected positive integer".into(),
        ));
    }
    let allow_stacking = bool_field(obj.get("allow_stacking"), false, "allow_stacking")?;
    let movement_mode = string_field(obj.get("movement_mode"), "mean", "movement_mode")?;
    let mode = string_field(obj.get("mode"), "ize", "mode")?;
    let mut plants = Vec::new();
    let mut ids = HashSet::new();
    let mut occupied_plant_layers: HashSet<(u8, u8, String)> = HashSet::new();
    let plant_values = obj
        .get("plants")
        .and_then(Value::as_array)
        .ok_or_else(|| InputError::Invalid("plants: expected array".into()))?;
    for (i, value) in plant_values.iter().enumerate() {
        let p = value
            .as_object()
            .ok_or_else(|| InputError::Invalid(format!("plants[{i}]: expected object")))?;
        let id = string_field(p.get("id"), &format!("p{}", i + 1), "plant.id")?;
        if !ids.insert(id.clone()) {
            return Err(InputError::Invalid(format!("duplicate id: {id}")));
        }
        let r = row(p.get("row"), &format!("plants[{i}].row"))?;
        let c = col(p.get("col"), &format!("plants[{i}].col"))?;
        let kind = string_field(p.get("type"), "peashooter", "plant.type")?;
        let footprint = if kind == "cob_cannon" {
            if c >= 9 {
                return Err(InputError::Invalid(format!(
                    "plants[{i}].col: cob_cannon occupies columns col and col+1; left column must be 1..8"
                )));
            }
            vec![c, c + 1]
        } else {
            vec![c]
        };
        let default_hp = plant_default_hp(&kind);
        let default_cooldown = plant_default_cooldown(&kind);
        let layer = string_field(p.get("layer"), plant_default_layer(&kind), "plant.layer")?;
        if !allow_stacking {
            for footprint_col in &footprint {
                let slot = (r, *footprint_col, layer.clone());
                if occupied_plant_layers.contains(&slot) {
                    return Err(InputError::Invalid(format!(
                        "plants[{i}]: duplicate plant layer or cob cannon footprint; set allow_stacking=true for explicit same-layer stacking"
                    )));
                }
            }
            for footprint_col in &footprint {
                occupied_plant_layers.insert((r, *footprint_col, layer.clone()));
            }
        }
        plants.push(Plant {
            id,
            kind,
            row: r,
            col: c,
            footprint,
            hp: i64_field(p.get("hp"), i64::from(default_hp), "plant.hp")? as i32,
            cooldown: u64_field(p.get("cooldown"), default_cooldown, "plant.cooldown")? as u32,
            state_timer: u64_field(p.get("state_timer"), 0, "plant.state_timer")? as u32,
            layer,
        });
    }
    let mut zombies = Vec::new();
    let zombie_values = obj
        .get("zombies")
        .and_then(Value::as_array)
        .ok_or_else(|| InputError::Invalid("zombies: expected array".into()))?;
    for (i, value) in zombie_values.iter().enumerate() {
        let z = value
            .as_object()
            .ok_or_else(|| InputError::Invalid(format!("zombies[{i}]: expected object")))?;
        let id = string_field(z.get("id"), &format!("z{}", i + 1), "zombie.id")?;
        if !ids.insert(id.clone()) {
            return Err(InputError::Invalid(format!("duplicate id: {id}")));
        }
        let r = row(z.get("row"), &format!("zombies[{i}].row"))?;
        let has_col = z.contains_key("col");
        let has_x = z.contains_key("x");
        if has_col == has_x {
            return Err(InputError::Invalid(format!(
                "zombies[{i}]: specify exactly one of col or x"
            )));
        }
        let kind = string_field(z.get("type"), "normal", "zombie.type")?;
        let offset = spawn_offset(&kind);
        let (x, c) = if has_col {
            let c = col(z.get("col"), &format!("zombies[{i}].col"))?;
            (40.0 + offset + 80.0 * f64::from(c - 1), c)
        } else {
            let x = f64_field(z.get("x"), 680.0, &format!("zombies[{i}].x"))?;
            let c = ((x - 40.0 - offset) / 80.0).round().clamp(0.0, 8.0) as u8 + 1;
            (x, c)
        };
        let default_hp = zombie_default_hp(&kind);
        let default_helmet = zombie_default_helmet(&kind);
        let default_shield = zombie_default_shield(&kind);
        let tool = bool_field(z.get("tool"), true, "zombie.tool")?;
        // A pole without its tool has already spent the vault and walks at
        // the ordinary zombie speed; the Rust slice does not model the jump.
        let default_speed = if kind == "pogo" && !tool {
            0.45
        } else if (kind == "pole_vaulting" || kind == "balloon") && !tool {
            0.143
        } else {
            zombie_default_speed(&kind)
        };
        zombies.push(Zombie {
            id,
            kind,
            row: r,
            col: c,
            x,
            x_fp: (x * 1000.0).round() as i64,
            speed_fp: (f64_field(z.get("speed"), default_speed, "zombie.speed")? * 1000.0).round()
                as i64,
            hp: i64_field(z.get("hp"), i64::from(default_hp), "zombie.hp")? as i32,
            helmet_hp: i64_field(
                z.get("helmet_hp"),
                i64::from(default_helmet),
                "zombie.helmet_hp",
            )? as i32,
            shield_hp: i64_field(
                z.get("shield_hp"),
                i64::from(default_shield),
                "zombie.shield_hp",
            )? as i32,
            speed: f64_field(z.get("speed"), default_speed, "zombie.speed")?,
            age: u64_field(z.get("age"), 0, "zombie.age")?,
            chilled: u64_field(z.get("chilled"), 0, "zombie.chilled")? as u32,
            headless: bool_field(z.get("headless"), false, "zombie.headless")?,
            hypnotized: bool_field(z.get("hypnotized"), false, "zombie.hypnotized")?,
            tool,
            underground: z.get("underground").and_then(Value::as_bool),
            status: UnitStatus::Active,
        });
    }
    let mut brains = Vec::new();
    let brain_values = obj
        .get("brains")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_else(|| vec![Value::from(3)]);
    for value in brain_values {
        if let Some(r) = value.as_u64() {
            if !(1..=5).contains(&r) {
                return Err(InputError::Invalid("brain row: expected 1..5".into()));
            }
            brains.push(Brain {
                row: r as u8,
                hp: 70,
            });
        } else {
            let b = value
                .as_object()
                .ok_or_else(|| InputError::Invalid("brain: expected row or object".into()))?;
            brains.push(Brain {
                row: row(b.get("row"), "brain.row")?,
                hp: i64_field(b.get("hp"), 70, "brain.hp")? as i32,
            });
        }
    }
    if brains.is_empty() {
        return Err(InputError::Invalid("brains: expected at least one".into()));
    }
    Ok(Scenario {
        version,
        seed,
        max_frames,
        plants,
        zombies,
        brains,
        runs,
        allow_stacking,
        movement_mode,
        mode,
        rakes: grid_objects(obj.get("rakes"))?,
        ladders: grid_objects(obj.get("ladders"))?,
    })
}

fn grid_objects(value: Option<&Value>) -> Result<Vec<GridObject>, InputError> {
    let Some(values) = value else {
        return Ok(Vec::new());
    };
    let values = values
        .as_array()
        .ok_or_else(|| InputError::Invalid("grid objects: expected array".into()))?;
    values
        .iter()
        .map(|value| {
            let obj = value
                .as_object()
                .ok_or_else(|| InputError::Invalid("grid object: expected object".into()))?;
            Ok(GridObject {
                row: row(obj.get("row"), "grid.row")?,
                col: col(obj.get("col"), "grid.col")?,
            })
        })
        .collect()
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CoreState {
    pub frame: u64,
    pub plants: Vec<Plant>,
    pub zombies: Vec<Zombie>,
    pub brains: Vec<Brain>,
}

impl From<Scenario> for CoreState {
    fn from(s: Scenario) -> Self {
        Self {
            frame: 0,
            plants: s.plants,
            zombies: s.zombies,
            brains: s.brains,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CoreResult {
    pub winner: Option<String>,
    pub reason: Option<String>,
    pub frames: u64,
    pub state: CoreState,
}

impl CoreState {
    /// One deterministic movement-only tick.  Combat and special behavior are
    /// intentionally not implemented here yet; this boundary is used by the
    /// upcoming differential port and never exposed as a final prediction.
    pub fn step_motion(&mut self) {
        self.frame += 1;
        for z in &mut self.zombies {
            if z.status != UnitStatus::Active {
                continue;
            }
            let direction: i64 = if z.hypnotized { 1 } else { -1 };
            z.x_fp += direction * z.speed_fp;
            z.x = z.x_fp as f64 / 1000.0;
            z.age += 1;
            // This is the movement-only boundary.  The full Python model uses
            // type-specific house thresholds and brain-bite combat; those are
            // deliberately left for the next migration slice.
            if z.x <= -80.0 {
                z.status = UnitStatus::Exited;
            } else if z.x <= 20.0 && !z.hypnotized {
                z.status = UnitStatus::EnteredHouse;
            }
        }
    }

    /// Return the terminal predicate for the currently ported movement slice.
    /// A hostile zombie is considered on-board only while active and alive;
    /// hypnotized zombies do not block the plant-side terminal state.
    pub fn terminal(&self, mode: &str) -> Option<(String, String)> {
        if self.brains.iter().all(|brain| brain.hp <= 0) {
            return Some(("zombies".into(), "all_brains_eaten".into()));
        }
        let active_hostile = self
            .zombies
            .iter()
            .any(|z| z.status == UnitStatus::Active && z.hp > 0 && !z.hypnotized);
        if mode == "who_will_win" {
            let row_three_threat = self.zombies.iter().any(|z| {
                z.status == UnitStatus::Active
                    && z.hp > 0
                    && z.row == 3
                    && !z.hypnotized
                    && !z.headless
            });
            if !row_three_threat {
                return Some(("plants".into(), "no_row_3_threats".into()));
            }
        } else if !active_hostile {
            return Some(("plants".into(), "no_on_board_zombies".into()));
        }
        None
    }

    /// Run the currently ported movement-only slice and return a stable JSON
    /// result.  It is intentionally not wired into the production Python
    /// backend until differential projections pass for all migrated modules.
    pub fn run_motion(mut self, max_frames: u64, mode: &str) -> CoreResult {
        if let Some((winner, reason)) = self.terminal(mode) {
            return CoreResult {
                winner: Some(winner),
                reason: Some(reason),
                frames: self.frame,
                state: self,
            };
        }
        while self.frame < max_frames {
            self.step_motion();
            if let Some((winner, reason)) = self.terminal(mode) {
                return CoreResult {
                    winner: Some(winner),
                    reason: Some(reason),
                    frames: self.frame,
                    state: self,
                };
            }
        }
        CoreResult {
            winner: None,
            reason: Some("max_frames_reached".into()),
            frames: self.frame,
            state: self,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct SimpleProjectile {
    pub row: u8,
    pub kind: String,
    pub x: f64,
    #[serde(skip)]
    pub x_fp: i64,
    pub damage: i32,
    pub active: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct SimpleState {
    pub frame: u64,
    pub mode: String,
    pub plants: Vec<Plant>,
    pub zombies: Vec<Zombie>,
    pub brains: Vec<Brain>,
    pub projectiles: Vec<SimpleProjectile>,
    pub events: std::collections::BTreeMap<String, u64>,
    pub rakes: Vec<GridObject>,
    pub ladders: Vec<GridObject>,
}

impl From<Scenario> for SimpleState {
    fn from(s: Scenario) -> Self {
        Self {
            frame: 0,
            mode: s.mode,
            plants: s.plants,
            zombies: s.zombies,
            brains: s.brains,
            projectiles: Vec::new(),
            events: std::collections::BTreeMap::new(),
            rakes: s.rakes,
            ladders: s.ladders,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct SimpleResult {
    pub winner: String,
    pub reason: String,
    pub frames: u64,
    pub state: SimpleState,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct SimpleBatchRun {
    pub run_index: u32,
    pub seed: i64,
    pub result: SimpleResult,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct SimpleBatchResult {
    pub batch: bool,
    pub runs: u32,
    pub seed: i64,
    pub model: String,
    pub approximate: bool,
    pub seed_strategy: String,
    pub parallel_workers: usize,
    pub outcomes: std::collections::BTreeMap<String, BatchOutcome>,
    pub results: Vec<SimpleBatchRun>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BatchOutcome {
    pub count: u32,
    pub probability: f64,
}

/// Run independent replicas of the migrated simple slice in parallel.
///
/// Each replica receives the same parsed scenario with a signed-i64 wrapping
/// seed (`base_seed + run_index`).  Rayon may complete replicas out of order,
/// so the result vector is explicitly sorted by `run_index` before returning.
/// This function is intentionally scoped to the differential-tested simple
/// slice; the Python batch implementation remains the semantic fallback for
/// unsupported mechanics and richer event streaming.
pub fn run_simple_batch(scenario: Scenario, workers: usize) -> SimpleBatchResult {
    let runs = scenario.runs.max(1);
    let worker_count = workers.max(1).min(runs as usize);
    let run_indices: Vec<u32> = (0..runs).collect();
    let execute = || {
        run_indices
            .par_iter()
            .map(|&run_index| {
                let mut replica = scenario.clone();
                replica.seed = scenario.seed.wrapping_add(i64::from(run_index));
                replica.runs = 1;
                let seed = replica.seed;
                let result = SimpleState::from(replica).run(scenario.max_frames);
                SimpleBatchRun {
                    run_index,
                    seed,
                    result,
                }
            })
            .collect::<Vec<_>>()
    };
    // Build a local pool so callers can choose a deterministic worker count
    // without mutating Rayon’s global pool (important for embedding/tests).
    let mut results = rayon::ThreadPoolBuilder::new()
        .num_threads(worker_count)
        .build()
        .map(|pool| pool.install(execute))
        .unwrap_or_else(|_| execute());
    results.sort_by_key(|row| row.run_index);

    let mut counts = std::collections::BTreeMap::<String, u32>::from([
        ("plants".into(), 0),
        ("zombies".into(), 0),
        ("undecided".into(), 0),
    ]);
    for row in &results {
        *counts.entry(row.result.winner.clone()).or_default() += 1;
    }
    let outcomes = counts
        .into_iter()
        .map(|(winner, count)| {
            (
                winner,
                BatchOutcome {
                    count,
                    probability: f64::from(count) / f64::from(runs),
                },
            )
        })
        .collect();
    SimpleBatchResult {
        batch: true,
        runs,
        seed: scenario.seed,
        model: "rust-simple-slice".into(),
        approximate: true,
        seed_strategy: "signed_int64_wrap(base_seed + zero_based_run_index)".into(),
        parallel_workers: worker_count,
        outcomes,
        results,
    }
}

fn plant_x_fp(col: u8) -> i64 {
    40_000 + 80_000 * i64::from(col.saturating_sub(1))
}

impl SimpleState {
    fn terminal(&self) -> Option<(String, String)> {
        if self.brains.iter().all(|b| b.hp <= 0) {
            return Some(("zombies".into(), "all_brains_eaten".into()));
        }
        if self.mode == "who_will_win" {
            let row_three_threat = self.zombies.iter().any(|z| {
                z.status == UnitStatus::Active
                    && z.hp > 0
                    && z.row == 3
                    && !z.hypnotized
                    && !z.headless
            });
            if !row_three_threat {
                return Some(("plants".into(), "no_row_3_threats".into()));
            }
            return None;
        }
        if !self
            .zombies
            .iter()
            .any(|z| z.status == UnitStatus::Active && z.hp > 0 && !z.hypnotized)
        {
            return Some(("plants".into(), "no_on_board_zombies".into()));
        }
        None
    }
    /// Deterministic pea-vs-normal slice; special handlers are intentionally
    /// excluded until their corresponding migration gate is ported.
    pub fn step(&mut self) {
        self.frame += 1;
        // COB cannon arming/reload is the only part of its attack state that
        // this slice can verify without reproducing the mouse-targeted lob.
        // Keep the counter observable and leave projectile/splash behavior to
        // the Python fallback.
        for p in &mut self.plants {
            if p.hp > 0 && p.kind == "cob_cannon" && p.cooldown > 0 {
                p.cooldown -= 1;
            }
        }
        let mut fired = 0_u64;
        let mut squash_hits = 0_u64;
        let mut potato_kills = 0_u64;
        let mut potato_explosions = 0_u64;
        let mut cherry_kills = 0_u64;
        let mut cherry_explosions = 0_u64;
        let mut jalapeno_kills = 0_u64;
        let mut jalapeno_explosions = 0_u64;
        let mut spikeweed_pulses = 0_u64;
        let mut spikerock_pulses = 0_u64;
        let mut hazard_kills = 0_u64;
        let mut hazard_damage = 0_u64;
        let mut fume_pulses = 0_u64;
        let mut fume_damage = 0_u64;
        for pi in 0..self.plants.len() {
            if self.plants[pi].hp <= 0 || self.plants[pi].kind != "cherry_bomb" {
                continue;
            }
            if self.plants[pi].state_timer == 0 {
                self.plants[pi].state_timer = 100;
            }
            self.plants[pi].state_timer -= 1;
            if self.plants[pi].state_timer == 0 {
                let px_fp = plant_x_fp(self.plants[pi].col);
                let row = self.plants[pi].row;
                for z in &mut self.zombies {
                    if z.status == UnitStatus::Active
                        && z.hp > 0
                        && !z.hypnotized
                        && (i16::from(z.row) - i16::from(row)).abs() <= 1
                        && (z.x_fp - px_fp).abs() <= 115_000
                    {
                        z.hp = 0;
                        z.status = UnitStatus::Dead;
                        cherry_kills += 1;
                    }
                }
                self.plants[pi].hp = 0;
                cherry_explosions += 1;
            }
        }
        // Jalapeno arms for 100 frames, then burns every hostile zombie and
        // removes persistent ladders on its row.  It is intentionally a
        // simple instant row effect; ice-ball/boss interactions remain in
        // the Python oracle.
        for pi in 0..self.plants.len() {
            if self.plants[pi].hp <= 0 || self.plants[pi].kind != "jalapeno" {
                continue;
            }
            if self.plants[pi].state_timer == 0 {
                self.plants[pi].state_timer = 100;
            }
            self.plants[pi].state_timer -= 1;
            if self.plants[pi].state_timer == 0 {
                let row = self.plants[pi].row;
                for z in &mut self.zombies {
                    if z.status == UnitStatus::Active && z.hp > 0 && !z.hypnotized && z.row == row {
                        z.hp = 0;
                        z.status = UnitStatus::Dead;
                        jalapeno_kills += 1;
                    }
                }
                self.ladders.retain(|ladder| ladder.row != row);
                self.plants[pi].hp = 0;
                jalapeno_explosions += 1;
            }
        }
        // Potato mine arms on contact and destroys itself.  Once triggered,
        // the simple slice applies its row-wide lethal blast to active hostile
        // zombies; underground/special targetability remains a later slice.
        for pi in 0..self.plants.len() {
            if self.plants[pi].hp <= 0 || self.plants[pi].kind != "potato_mine" {
                continue;
            }
            let px_fp = plant_x_fp(self.plants[pi].col);
            let triggered = self.zombies.iter().any(|z| {
                z.status == UnitStatus::Active
                    && z.hp > 0
                    && !z.hypnotized
                    && z.row == self.plants[pi].row
                    && z.x_fp >= px_fp
                    && z.x_fp - px_fp <= 55_000
            });
            if triggered {
                for z in &mut self.zombies {
                    if z.status == UnitStatus::Active
                        && z.hp > 0
                        && !z.hypnotized
                        && z.row == self.plants[pi].row
                    {
                        z.hp = 0;
                        z.status = UnitStatus::Dead;
                        potato_kills += 1;
                    }
                }
                self.plants[pi].hp = 0;
                potato_explosions += 1;
            }
        }
        // Ground hazards are never bite targets.  They arm when a zombie's
        // hitbox overlaps the cell, then pulse after the native wind-up:
        // spikeweed at timer 75 and spikerock at timers 70 and 32.  The
        // shield is bypassed, while a carried helmet still absorbs damage,
        // matching Simulator.damage(..., bypass=True).
        for pi in 0..self.plants.len() {
            let kind = self.plants[pi].kind.clone();
            if self.plants[pi].hp <= 0 || !matches!(kind.as_str(), "spikeweed" | "spikerock") {
                continue;
            }
            let px_fp = plant_x_fp(self.plants[pi].col);
            let row = self.plants[pi].row;
            let in_range = |z: &Zombie, strict: bool| {
                z.status == UnitStatus::Active
                    && z.hp > 0
                    && !z.hypnotized
                    && z.row == row
                    // Normal/screen-door hitbox in this slice is origin
                    // +[36,78]; use overlap rather than origin-only checks.
                    && if strict {
                        z.x_fp + 36_000 < px_fp + 50_000
                            && z.x_fp + 78_000 > px_fp + 20_000
                    } else {
                        z.x_fp + 36_000 <= px_fp + 50_000
                            && z.x_fp + 78_000 >= px_fp + 20_000
                    }
            };
            // `state_timer == 0` is the public ready state.  A positive
            // timer denotes the private attacking animation; keeping this
            // implicit avoids widening the stable JSON state schema.
            if self.plants[pi].state_timer == 0 {
                if self.zombies.iter().any(|z| in_range(z, false)) {
                    self.plants[pi].state_timer = 100;
                }
                continue;
            }
            if self.plants[pi].state_timer > 0 {
                self.plants[pi].state_timer -= 1;
            }
            let pulse = if kind == "spikeweed" {
                self.plants[pi].state_timer == 75
            } else {
                self.plants[pi].state_timer == 70 || self.plants[pi].state_timer == 32
            };
            if pulse {
                let ids: Vec<usize> = self
                    .zombies
                    .iter()
                    .enumerate()
                    .filter(|(_, z)| in_range(z, true))
                    .map(|(zi, _)| zi)
                    .collect();
                for zi in ids.iter().copied() {
                    let z = &mut self.zombies[zi];
                    hazard_damage += 1;
                    let mut remaining = 20_i32;
                    if z.helmet_hp > 0 {
                        let absorbed = z.helmet_hp.min(remaining);
                        z.helmet_hp -= absorbed;
                        remaining -= absorbed;
                    }
                    z.hp = (z.hp - remaining).max(0);
                    if z.hp == 0 {
                        z.status = UnitStatus::Dead;
                        hazard_kills += 1;
                    }
                }
                if !ids.is_empty() {
                    if kind == "spikeweed" {
                        spikeweed_pulses += 1;
                    } else {
                        spikerock_pulses += 1;
                    }
                }
            }
        }
        // Fume-shroom is a deterministic same-row cone in this slice.  Its
        // `both` damage consumes shield and applies the full 20 damage to the
        // body path (with helmet absorption), matching the Python oracle;
        // animation-driven wind-up remains represented by explicit cooldown.
        for pi in 0..self.plants.len() {
            if self.plants[pi].hp <= 0 || self.plants[pi].kind != "fume_shroom" {
                continue;
            }
            if self.plants[pi].cooldown > 0 {
                self.plants[pi].cooldown -= 1;
            }
            if self.plants[pi].cooldown != 0 {
                continue;
            }
            let px_fp = plant_x_fp(self.plants[pi].col);
            let row = self.plants[pi].row;
            for z in &mut self.zombies {
                if z.status != UnitStatus::Active
                    || z.hp <= 0
                    || z.hypnotized
                    || z.row != row
                    || !(z.x_fp + 36_000 < px_fp + 400_000 && z.x_fp + 78_000 > px_fp + 60_000)
                {
                    continue;
                }
                let mut remaining = 20_i32;
                if z.shield_hp > 0 {
                    let absorbed = z.shield_hp.min(remaining);
                    z.shield_hp -= absorbed;
                    if z.shield_hp == 0 {
                        *self.events.entry("armor_lost".into()).or_default() += 1;
                    }
                }
                if z.helmet_hp > 0 {
                    let absorbed = z.helmet_hp.min(remaining);
                    z.helmet_hp -= absorbed;
                    remaining -= absorbed;
                    if z.helmet_hp == 0 {
                        *self.events.entry("armor_lost".into()).or_default() += 1;
                    }
                }
                z.hp = (z.hp - remaining).max(0);
                fume_damage += 1;
                if z.hp == 0 {
                    z.status = UnitStatus::Dead;
                }
            }
            self.plants[pi].cooldown = 150;
            fume_pulses += 1;
        }
        // High-health shells use the same bite pipeline; squash is a one-shot
        // close-range attacker in this first special-mechanism slice.
        for pi in 0..self.plants.len() {
            if self.plants[pi].hp <= 0 || self.plants[pi].kind != "squash" {
                continue;
            }
            let px_fp = plant_x_fp(self.plants[pi].col);
            if let Some(z) = self.zombies.iter_mut().find(|z| {
                z.status == UnitStatus::Active
                    && z.hp > 0
                    && !z.hypnotized
                    && z.row == self.plants[pi].row
                    && z.x_fp >= px_fp
                    && z.x_fp - px_fp <= 120_000
            }) {
                z.hp = 0;
                z.status = UnitStatus::Dead;
                self.plants[pi].hp = 0;
                squash_hits += 1;
            }
        }
        for p in &mut self.plants {
            if p.hp <= 0
                || !matches!(
                    p.kind.as_str(),
                    "peashooter" | "snow_pea" | "repeater" | "threepeater" | "split_pea"
                )
            {
                continue;
            }
            if p.cooldown > 0 {
                p.cooldown -= 1;
            }
            if p.cooldown == 0 {
                let kind = if p.kind == "snow_pea" { "ice" } else { "pea" };
                let rows: Vec<u8> = if p.kind == "threepeater" {
                    [p.row.saturating_sub(1), p.row, p.row.saturating_add(1)]
                        .into_iter()
                        .filter(|row| (1..=5).contains(row))
                        .collect()
                } else {
                    vec![
                        p.row;
                        if matches!(p.kind.as_str(), "repeater" | "split_pea") {
                            2
                        } else {
                            1
                        }
                    ]
                };
                for (shot_index, row) in rows.iter().copied().enumerate() {
                    let backward = p.kind == "split_pea" && shot_index == 1;
                    self.projectiles.push(SimpleProjectile {
                        row,
                        kind: if backward { "pea_back" } else { kind }.into(),
                        x: p.x() + if backward { -27.0 } else { 50.0 },
                        x_fp: plant_x_fp(p.col) + if backward { -27_000 } else { 50_000 },
                        damage: 20,
                        active: true,
                    });
                }
                p.cooldown = 150;
                fired += rows.len() as u64;
            }
        }
        for q in &mut self.projectiles {
            if q.active {
                q.x_fp += if q.kind == "pea_back" { -8_000 } else { 8_000 };
                q.x = q.x_fp as f64 / 1000.0;
            }
        }
        let mut hits = 0_u64;
        let mut deaths = squash_hits + potato_kills + cherry_kills + jalapeno_kills + hazard_kills;
        let mut chilled = 0_u64;
        for qi in 0..self.projectiles.len() {
            if !self.projectiles[qi].active {
                continue;
            }
            let (row, x_fp, damage, kind) = (
                self.projectiles[qi].row,
                self.projectiles[qi].x_fp,
                self.projectiles[qi].damage,
                self.projectiles[qi].kind.clone(),
            );
            if let Some(z) = self.zombies.iter_mut().find(|z| {
                z.status == UnitStatus::Active
                    && z.hp > 0
                    && z.row == row
                    && (z.x_fp - x_fp).abs() <= 25_000
            }) {
                // Match Simulator.damage's normal pea path: a projectile
                // consumes the zombie's shield first, then helmet, then
                // body HP.  `both`/bypass attacks are outside this simple
                // slice, so every projectile follows the guarded path.
                let mut remaining = damage.max(0);
                if z.shield_hp > 0 && remaining > 0 {
                    let absorbed = z.shield_hp.min(remaining);
                    z.shield_hp -= absorbed;
                    remaining -= absorbed;
                    if z.shield_hp == 0 {
                        *self.events.entry("armor_lost".into()).or_default() += 1;
                    }
                }
                if z.helmet_hp > 0 && remaining > 0 {
                    let absorbed = z.helmet_hp.min(remaining);
                    z.helmet_hp -= absorbed;
                    remaining -= absorbed;
                    if z.helmet_hp == 0 {
                        *self.events.entry("armor_lost".into()).or_default() += 1;
                    }
                }
                z.hp = (z.hp - remaining).max(0);
                self.projectiles[qi].active = false;
                hits += 1;
                if kind == "ice" {
                    z.chilled = 300;
                    chilled += 1;
                }
                if z.hp == 0 {
                    z.status = UnitStatus::Dead;
                    deaths += 1;
                }
            }
        }
        self.projectiles.retain(|q| q.active && q.x < 900.0);
        let mut bites = 0_u64;
        let mut brain_eaten = 0_u64;
        let mut digger_emerged = 0_u64;
        let mut ladder_placed = 0_u64;
        for zi in 0..self.zombies.len() {
            if self.zombies[zi].status != UnitStatus::Active || self.zombies[zi].hp <= 0 {
                continue;
            }
            self.zombies[zi].age += 1;
            if self.zombies[zi].chilled > 0 {
                self.zombies[zi].chilled -= 1;
            }
            // A charmed zombie is friendly: it walks toward the right edge,
            // never bites plants/brains, and does not block the hostile-board
            // terminal predicate.  Combat between friendly and hostile
            // zombies belongs to a later social-special slice.
            if self.zombies[zi].hypnotized {
                self.zombies[zi].x_fp += self.zombies[zi].speed_fp.max(1);
                self.zombies[zi].x = self.zombies[zi].x_fp as f64 / 1000.0;
                if self.zombies[zi].x_fp > 850_000 {
                    self.zombies[zi].status = UnitStatus::Exited;
                    *self.events.entry("zombie_exited".into()).or_default() += 1;
                }
                continue;
            }
            if self.zombies[zi].underground == Some(true) {
                if self.zombies[zi].age >= 2 {
                    self.zombies[zi].underground = Some(false);
                    digger_emerged += 1;
                }
                continue;
            }
            if self.zombies[zi].kind == "ladder"
                && self.zombies[zi].tool
                && self.zombies[zi].shield_hp > 0
            {
                let zx_fp = self.zombies[zi].x_fp;
                let row = self.zombies[zi].row;
                if let Some((_, plant)) = self.plants.iter().enumerate().find(|(_, p)| {
                    p.hp > 0
                        && matches!(p.kind.as_str(), "wallnut" | "tallnut")
                        && p.row == row
                        && zx_fp >= plant_x_fp(p.col) - 60_000
                        && zx_fp <= plant_x_fp(p.col) + 70_000
                        && !self
                            .ladders
                            .iter()
                            .any(|l| l.row == p.row && l.col == p.col)
                }) {
                    self.ladders.push(GridObject {
                        row: plant.row,
                        col: plant.col,
                    });
                    self.zombies[zi].tool = false;
                    self.zombies[zi].shield_hp = 0;
                    ladder_placed += 1;
                    continue;
                }
            }
            let zx_fp = self.zombies[zi].x_fp;
            let row = self.zombies[zi].row;
            let target = self
                .plants
                .iter()
                .enumerate()
                .find(|(_, p)| {
                    let px_fp = plant_x_fp(p.col);
                    p.hp > 0
                        && p.row == row
                        && !matches!(p.kind.as_str(), "spikeweed" | "spikerock")
                        && !self
                            .ladders
                            .iter()
                            .any(|l| l.row == p.row && l.col == p.col)
                        && zx_fp >= px_fp
                        && zx_fp - px_fp <= 60_000
                })
                .map(|(i, _)| i);
            if let Some(pi) = target {
                if self.zombies[zi].age % 4 == 0 {
                    self.plants[pi].hp = (self.plants[pi].hp - 4).max(0);
                    bites += 1;
                }
            } else {
                let speed = if self.zombies[zi].chilled > 0 {
                    (self.zombies[zi].speed_fp / 2).max(1)
                } else {
                    self.zombies[zi].speed_fp
                };
                self.zombies[zi].x_fp -= speed;
                self.zombies[zi].x = self.zombies[zi].x_fp as f64 / 1000.0;
                if self.zombies[zi].x_fp <= 20_000 {
                    self.zombies[zi].status = UnitStatus::EnteredHouse;
                    if let Some(brain) = self.brains.iter_mut().find(|b| b.row == row && b.hp > 0) {
                        brain.hp = 0;
                        brain_eaten += 1;
                    }
                }
            }
        }
        // A lawn rake is a one-shot pre-placed object.  The Python engine
        // triggers it after movement; mirror its 63x80 cell rectangle here.
        let mut rake_hits = 0_u64;
        self.rakes.retain(|rake| {
            let rx_fp = plant_x_fp(rake.col);
            let hit = self.zombies.iter_mut().find(|z| {
                z.status == UnitStatus::Active
                    && z.hp > 0
                    && !z.hypnotized
                    && z.row == rake.row
                    && z.x_fp >= rx_fp - 60_000
                    && z.x_fp <= rx_fp + 63_000
            });
            if let Some(z) = hit {
                z.hp = 0;
                z.status = UnitStatus::Dead;
                rake_hits += 1;
                false
            } else {
                true
            }
        });
        for (name, count) in [
            ("projectile_fired", fired),
            ("projectile_hit", hits),
            ("zombie_died", deaths),
            ("plant_bitten", bites),
            ("brain_eaten", brain_eaten),
            ("squash_impact", squash_hits),
            ("explosion", potato_explosions),
            ("explosion", cherry_explosions),
            ("explosion", jalapeno_explosions),
            ("spikeweed_pulse", spikeweed_pulses),
            ("spikerock_pulse", spikerock_pulses),
            ("damage", hazard_damage),
            ("fume", fume_pulses),
            ("damage", fume_damage),
            ("chill_applied", chilled),
            ("digger_emerged", digger_emerged),
            ("rake_triggered", rake_hits),
            ("zombie_died", rake_hits),
            ("ladder_placed", ladder_placed),
        ] {
            if count > 0 {
                *self.events.entry(name.into()).or_default() += count;
            }
        }
    }
    pub fn run(&mut self, max_frames: u64) -> SimpleResult {
        if let Some((winner, reason)) = self.terminal() {
            return SimpleResult {
                winner,
                reason,
                frames: self.frame,
                state: self.clone(),
            };
        }
        while self.frame < max_frames {
            self.step();
            if let Some((winner, reason)) = self.terminal() {
                return SimpleResult {
                    winner,
                    reason,
                    frames: self.frame,
                    state: self.clone(),
                };
            }
        }
        SimpleResult {
            winner: "undecided".into(),
            reason: "max_frames_reached".into(),
            frames: self.frame,
            state: self.clone(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn sample() -> &'static str {
        r#"{"seed":42,"brains":[3],"plants":[{"type":"repeater","row":3,"col":2}],"zombies":[{"type":"normal","row":3,"col":7},{"type":"digger","row":3,"col":7,"underground":true}]}"#
    }
    #[test]
    fn parses_and_preserves_overlap() {
        let s = parse_scenario(sample()).unwrap();
        assert_eq!(s.zombies.len(), 2);
        assert_eq!(s.zombies[0].col, s.zombies[1].col);
    }
    #[test]
    fn normalizes_pixel_x() {
        let s = parse_scenario(sample()).unwrap();
        assert!((s.zombies[0].x - 490.0).abs() < f64::EPSILON);
    }
    #[test]
    fn rejects_both_coordinates() {
        let bad = r#"{"zombies":[{"type":"normal","row":3,"col":7,"x":490}]}"#;
        assert!(parse_scenario(bad).is_err());
    }

    #[test]
    fn rejects_duplicate_plant_layer_without_stacking() {
        let bad = r#"{"plants":[{"type":"wallnut","row":3,"col":2},{"type":"peashooter","row":3,"col":2}],"zombies":[],"brains":[3]}"#;
        let err = parse_scenario(bad).expect_err("same-layer overlap must be rejected");
        assert!(err.to_string().contains("allow_stacking=true"));
    }

    #[test]
    fn allows_duplicate_plant_layer_when_stacking_is_explicit() {
        let text = r#"{"allow_stacking":true,"plants":[{"type":"wallnut","row":3,"col":2},{"type":"peashooter","row":3,"col":2}],"zombies":[],"brains":[3]}"#;
        let scenario = parse_scenario(text).expect("explicit stacking should preserve overlap");
        assert_eq!(scenario.plants.len(), 2);
    }

    #[test]
    fn preserves_cob_cannon_two_cell_footprint() {
        let text =
            r#"{"plants":[{"type":"cob_cannon","row":3,"col":8}],"zombies":[],"brains":[3]}"#;
        let s = parse_scenario(text).unwrap();
        assert_eq!(s.plants[0].footprint, vec![8, 9]);
    }

    #[test]
    fn simple_cob_cannon_arms_without_ballistic_fire() {
        let text = r#"{"max_frames":1,"plants":[{"type":"cob_cannon","row":3,"col":2,"cooldown":500}],"zombies":[{"type":"normal","row":3,"x":600}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        s.step();
        assert_eq!(s.plants[0].footprint, vec![2, 3]);
        assert_eq!(s.plants[0].cooldown, 499);
        assert!(s.projectiles.is_empty());
        assert!(!s.events.contains_key("cob_fired"));
    }

    #[test]
    fn rejects_cob_cannon_in_last_column() {
        let text =
            r#"{"plants":[{"type":"cob_cannon","row":3,"col":9}],"zombies":[],"brains":[3]}"#;
        let error = parse_scenario(text).unwrap_err().to_string();
        assert!(error.contains("cob_cannon occupies columns col and col+1"));
    }
    #[test]
    fn movement_boundary_is_deterministic() {
        let mut s = CoreState::from(parse_scenario(sample()).unwrap());
        s.step_motion();
        assert_eq!(s.frame, 1);
        assert!((s.zombies[0].x - 489.857).abs() < 1e-9);
    }
    #[test]
    fn repeated_steps_advance_age_and_terminal_when_empty() {
        let mut s = CoreState::from(parse_scenario(sample()).unwrap());
        s.zombies.clear();
        assert_eq!(
            s.terminal("ize"),
            Some(("plants".into(), "no_on_board_zombies".into()))
        );
        let result = s.run_motion(3, "ize");
        assert_eq!(result.frames, 0);
        assert_eq!(result.winner.as_deref(), Some("plants"));
    }

    #[test]
    fn brain_death_has_priority_over_empty_board() {
        let mut s = CoreState::from(parse_scenario(sample()).unwrap());
        s.brains[0].hp = 0;
        assert_eq!(
            s.terminal("ize"),
            Some(("zombies".into(), "all_brains_eaten".into()))
        );
    }
    #[test]
    fn simple_pea_projectile_damages_normal_zombie() {
        let text = r#"{"max_frames":1,"plants":[{"type":"peashooter","row":3,"col":1,"cooldown":0}],"zombies":[{"type":"normal","row":3,"col":2,"hp":270}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        s.step();
        assert_eq!(s.events.get("projectile_fired"), Some(&1));
        assert_eq!(s.zombies[0].hp, 250);
        assert_eq!(s.events.get("projectile_hit"), Some(&1));
    }

    #[test]
    fn simple_fixed_point_motion_does_not_accumulate_float_drift() {
        let text = r#"{"plants":[],"zombies":[{"type":"normal","row":3,"x":100.0,"speed":0.143}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        for _ in 0..7 {
            s.step();
        }
        assert_eq!(s.zombies[0].x_fp, 98_999);
        assert!((s.zombies[0].x - 98.999).abs() < 1e-9);
    }

    #[test]
    fn simple_nut_default_health_survives_one_bite() {
        let text = r#"{"plants":[{"type":"wallnut","row":3,"col":1}],"zombies":[{"type":"normal","row":3,"x":90,"age":3}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        s.step();
        assert_eq!(s.plants[0].hp, 3996);
    }

    #[test]
    fn simple_squash_one_shot_kills_close_zombie() {
        let text = r#"{"plants":[{"type":"squash","row":3,"col":1}],"zombies":[{"type":"normal","row":3,"x":90}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        s.step();
        assert_eq!(s.zombies[0].status, UnitStatus::Dead);
        assert_eq!(s.events.get("squash_impact"), Some(&1));
    }

    #[test]
    fn simple_potato_mine_explodes_on_contact_and_only_hits_its_row() {
        let text = r#"{"max_frames":1,"plants":[{"type":"potato_mine","row":3,"col":1}],"zombies":[{"type":"normal","row":3,"x":90},{"type":"normal","row":2,"x":90}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        s.step();
        assert_eq!(s.plants[0].hp, 0);
        assert_eq!(s.zombies[0].status, UnitStatus::Dead);
        assert_eq!(s.zombies[1].status, UnitStatus::Active);
        assert_eq!(s.events.get("explosion"), Some(&1));
        assert_eq!(s.events.get("zombie_died"), Some(&1));
    }

    #[test]
    fn simple_cherry_bomb_delayed_blast_hits_nearby_zombie() {
        let text = r#"{"max_frames":100,"plants":[{"type":"cherry_bomb","row":3,"col":3}],"zombies":[{"type":"normal","row":3,"col":4},{"type":"normal","row":3,"col":5}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        let result = s.run(100);
        assert_eq!(result.frames, 100);
        assert_eq!(s.plants[0].hp, 0);
        assert_eq!(s.zombies[0].status, UnitStatus::Dead);
        assert_eq!(s.zombies[1].status, UnitStatus::Active);
        assert_eq!(s.events.get("explosion"), Some(&1));
    }

    #[test]
    fn simple_ice_pea_applies_chill_state() {
        let text = r#"{"plants":[{"type":"snow_pea","row":3,"col":1}],"zombies":[{"type":"normal","row":3,"x":90}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        s.step();
        assert_eq!(s.zombies[0].chilled, 299);
        assert_eq!(s.events.get("chill_applied"), Some(&1));
    }

    #[test]
    fn simple_repeater_fires_two_projectiles() {
        let text = r#"{"plants":[{"type":"repeater","row":3,"col":1}],"zombies":[{"type":"normal","row":3,"x":90}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        s.step();
        assert_eq!(s.events.get("projectile_fired"), Some(&2));
        assert_eq!(s.events.get("projectile_hit"), Some(&2));
        assert_eq!(s.zombies[0].hp, 230);
    }

    #[test]
    fn simple_threepeater_fires_one_straight_pea_per_adjacent_row() {
        let text = r#"{"max_frames":1,"plants":[{"type":"threepeater","row":3,"col":1,"cooldown":0}],"zombies":[{"type":"normal","row":2,"x":90},{"type":"normal","row":3,"x":90},{"type":"normal","row":4,"x":90}],"brains":[2,3,4]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        s.step();
        assert_eq!(s.events.get("projectile_fired"), Some(&3));
        assert_eq!(s.events.get("projectile_hit"), Some(&3));
        assert_eq!(
            s.zombies.iter().map(|z| z.hp).collect::<Vec<_>>(),
            vec![250, 250, 250]
        );
    }

    #[test]
    fn simple_fume_pulse_hits_same_row_and_bypasses_shield_bodywise() {
        let text = r#"{"max_frames":1,"plants":[{"type":"fume_shroom","row":3,"col":1,"cooldown":0}],"zombies":[{"type":"screen_door","row":3,"x":200},{"type":"normal","row":3,"x":300},{"type":"normal","row":3,"x":404},{"type":"normal","row":2,"x":200}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        s.step();
        assert_eq!(s.events.get("fume"), Some(&1));
        assert_eq!(s.events.get("damage"), Some(&2));
        assert_eq!(s.zombies[0].shield_hp, 1080);
        assert_eq!(s.zombies[0].hp, 250);
        assert_eq!(s.zombies[1].hp, 250);
        assert_eq!(s.zombies[2].hp, 270);
        assert_eq!(s.zombies[3].hp, 270);
    }

    #[test]
    fn simple_pumpkin_shell_uses_catalog_health_and_bite_pipeline() {
        let text = r#"{"max_frames":1,"plants":[{"type":"pumpkin","row":3,"col":1}],"zombies":[{"type":"normal","row":3,"x":90,"age":3}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        assert_eq!(s.plants[0].hp, 4000);
        assert_eq!(s.plants[0].layer, "shell");
        s.step();
        assert_eq!(s.plants[0].hp, 3996);
    }

    #[test]
    fn simple_split_pea_fires_forward_and_backward_straight_projectiles() {
        let text = r#"{"max_frames":1,"plants":[{"type":"split_pea","row":3,"col":3,"cooldown":0}],"zombies":[{"type":"normal","row":3,"x":280},{"type":"normal","row":3,"x":170}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        s.step();
        assert_eq!(s.events.get("projectile_fired"), Some(&2));
        assert_eq!(s.events.get("projectile_hit"), Some(&2));
        assert_eq!(
            s.zombies.iter().map(|z| z.hp).collect::<Vec<_>>(),
            vec![250, 250]
        );
    }

    #[test]
    fn simple_pea_strips_helmet_before_body_damage() {
        let text = r#"{"plants":[{"type":"peashooter","row":3,"col":1}],"zombies":[{"type":"buckethead","row":3,"x":90,"hp":270,"helmet_hp":10}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        s.step();
        assert_eq!(
            (
                s.zombies[0].helmet_hp,
                s.zombies[0].shield_hp,
                s.zombies[0].hp
            ),
            (0, 0, 260)
        );
        assert_eq!(s.events.get("armor_lost"), Some(&1));
    }

    #[test]
    fn simple_pea_strips_shield_before_helmet_and_body() {
        let text = r#"{"plants":[{"type":"peashooter","row":3,"col":1}],"zombies":[{"type":"screen_door","row":3,"x":90,"hp":270,"shield_hp":10}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        s.step();
        assert_eq!(
            (
                s.zombies[0].helmet_hp,
                s.zombies[0].shield_hp,
                s.zombies[0].hp
            ),
            (0, 0, 260)
        );
        assert_eq!(s.events.get("armor_lost"), Some(&1));
    }

    #[test]
    fn simple_base_armor_zombies_use_catalog_defaults() {
        let text = r#"{"plants":[],"zombies":[
            {"type":"conehead","row":3,"x":90},
            {"type":"buckethead","row":3,"x":170},
            {"type":"screen_door","row":3,"x":250}],"brains":[3]}"#;
        let s = parse_scenario(text).unwrap();
        assert_eq!(
            s.zombies
                .iter()
                .map(|z| (z.hp, z.helmet_hp, z.shield_hp))
                .collect::<Vec<_>>(),
            vec![(270, 370, 0), (270, 1100, 0), (270, 0, 1100)]
        );
    }

    #[test]
    fn simple_football_defaults_use_catalog_armor_and_speed() {
        let text = r#"{"max_frames":1,"plants":[{"type":"peashooter","row":3,"col":1,"cooldown":0}],"zombies":[{"type":"football","row":3,"x":90}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        assert_eq!(s.zombies[0].helmet_hp, 1400);
        assert!((s.zombies[0].speed - 0.32).abs() < f64::EPSILON);
        s.step();
        assert_eq!(s.events.get("projectile_hit"), Some(&1));
        assert_eq!(s.zombies[0].helmet_hp, 1380);
        assert_eq!(s.zombies[0].hp, 270);
        // The football zombie is already in bite range of the shooter cell,
        // so the movement phase holds it in place after the direct hit.
        assert!((s.zombies[0].x - 90.0).abs() < 1e-9);
    }

    #[test]
    fn simple_newspaper_defaults_use_catalog_shield_and_speed() {
        let text = r#"{"max_frames":1,"plants":[],"zombies":[{"type":"newspaper","row":3,"x":500}],"brains":[3]}"#;
        let s = SimpleState::from(parse_scenario(text).unwrap());
        assert_eq!(s.zombies[0].shield_hp, 150);
        assert!((s.zombies[0].speed - 0.09).abs() < f64::EPSILON);
    }

    #[test]
    fn simple_newspaper_shield_break_keeps_body_damage_order_without_rage_animation() {
        let text = r#"{"max_frames":1,"plants":[{"type":"peashooter","row":3,"col":1,"cooldown":0}],"zombies":[{"type":"newspaper","row":3,"x":90,"shield_hp":20}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        s.step();
        assert_eq!(s.zombies[0].shield_hp, 0);
        assert_eq!(s.zombies[0].hp, 270);
        assert!((s.zombies[0].speed - 0.09).abs() < f64::EPSILON);
        assert_eq!(s.events.get("armor_lost"), Some(&1));
        // The simple slice deliberately has no reading/maddening phase field;
        // animation-driven speed escalation remains on the Python fallback.
    }

    #[test]
    fn simple_imp_defaults_use_catalog_health_and_speed() {
        let text = r#"{"max_frames":1,"plants":[],"zombies":[{"type":"imp","row":3,"x":500}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        assert_eq!(s.zombies[0].hp, 70);
        assert!((s.zombies[0].speed - 0.423).abs() < f64::EPSILON);
        s.step();
        assert!((s.zombies[0].x - 499.577).abs() < 1e-9);
    }

    #[test]
    fn simple_imp_accepts_pea_projectile_damage_without_throw_state() {
        let text = r#"{"max_frames":1,"plants":[{"type":"peashooter","row":3,"col":1,"cooldown":0}],"zombies":[{"type":"imp","row":3,"x":90}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        s.step();
        assert_eq!(s.zombies[0].hp, 50);
        assert_eq!(s.events.get("projectile_fired"), Some(&1));
        assert_eq!(s.events.get("projectile_hit"), Some(&1));
    }

    #[test]
    fn simple_pole_vault_defaults_use_catalog_health_and_speed() {
        let text = r#"{"max_frames":1,"plants":[],"zombies":[{"type":"pole_vaulting","row":3,"x":500}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        assert_eq!(s.zombies[0].hp, 500);
        assert!((s.zombies[0].speed - 0.32).abs() < f64::EPSILON);
        s.step();
        assert!((s.zombies[0].x - 499.68).abs() < 1e-9);
    }

    #[test]
    fn simple_spent_pole_walks_at_normal_speed() {
        let text = r#"{"max_frames":1,"plants":[],"zombies":[{"type":"pole_vaulting","row":3,"x":500,"tool":false}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        assert!((s.zombies[0].speed - 0.143).abs() < f64::EPSILON);
        s.step();
        assert!((s.zombies[0].x - 499.857).abs() < 1e-9);
    }

    #[test]
    fn simple_zamboni_defaults_walk_without_machine_targets() {
        let text = r#"{"max_frames":1,"plants":[],"zombies":[{"type":"zamboni","row":3,"x":800}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        assert_eq!(s.zombies[0].hp, 1350);
        assert!((s.zombies[0].speed - 0.25).abs() < f64::EPSILON);
        s.step();
        assert!((s.zombies[0].x - 799.75).abs() < 1e-9);
    }

    #[test]
    fn simple_popped_balloon_uses_normal_walk_defaults() {
        let text = r#"{"max_frames":1,"plants":[],"zombies":[{"type":"balloon","row":3,"x":500,"tool":false}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        assert_eq!(s.zombies[0].hp, 270);
        assert!((s.zombies[0].speed - 0.143).abs() < f64::EPSILON);
        s.step();
        assert!((s.zombies[0].x - 499.857).abs() < 1e-9);
    }

    #[test]
    fn simple_spent_pogo_uses_catalog_walk_defaults() {
        let text = r#"{"max_frames":1,"plants":[],"zombies":[{"type":"pogo","row":3,"x":500,"tool":false}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        assert_eq!(s.zombies[0].hp, 500);
        assert!((s.zombies[0].speed - 0.45).abs() < f64::EPSILON);
        s.step();
        assert!((s.zombies[0].x - 499.55).abs() < 1e-9);
    }

    #[test]
    fn simple_flag_defaults_use_catalog_speed_and_straight_pea_damage() {
        let text = r#"{"max_frames":1,"plants":[{"type":"peashooter","row":3,"col":1,"cooldown":0}],"zombies":[{"type":"flag","row":3,"x":90},{"type":"flag","row":3,"x":500}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        assert!((s.zombies[0].speed - 0.22).abs() < f64::EPSILON);
        s.step();
        assert_eq!(s.events.get("projectile_hit"), Some(&1));
        assert_eq!(s.zombies[0].hp, 250);
        assert!((s.zombies[1].x - 499.78).abs() < 1e-9);
    }

    #[test]
    fn simple_hypnotized_zombie_walks_right_without_attacking() {
        let text = r#"{"max_frames":3,"plants":[],"zombies":[{"id":"friend","type":"normal","row":3,"x":90,"speed":0.143,"hypnotized":true},{"id":"hostile","type":"normal","row":3,"x":500,"speed":0.143}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        let result = s.run(3);
        assert_eq!(result.winner, "undecided");
        assert_eq!(result.frames, 3);
        assert_eq!(s.zombies[0].x_fp, 90_429);
        assert_eq!(s.zombies[0].age, 3);
        assert_eq!(s.zombies[0].status, UnitStatus::Active);
        assert_eq!(s.zombies[1].x_fp, 499_571);
    }

    #[test]
    fn simple_who_will_win_only_considers_row_three_at_frame_zero() {
        let text = r#"{"mode":"who_will_win","max_frames":120,"plants":[],"zombies":[{"type":"normal","row":2,"x":500}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        let result = s.run(120);
        assert_eq!(result.frames, 0);
        assert_eq!(result.winner, "plants");
        assert_eq!(result.reason, "no_row_3_threats");
        assert_eq!(s.mode, "who_will_win");
    }

    #[test]
    fn simple_digger_emerges_after_two_underground_ticks() {
        let text = r#"{"max_frames":3,"plants":[],"zombies":[{"type":"digger","row":3,"x":90,"underground":true}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        for _ in 0..3 {
            s.step();
        }
        assert_eq!(s.zombies[0].underground, Some(false));
        assert_eq!(s.events.get("digger_emerged"), Some(&1));
    }

    #[test]
    fn simple_rake_triggers_on_first_occupied_cell() {
        let text = r#"{"max_frames":1,"rakes":[{"row":3,"col":8}],"plants":[],"zombies":[{"type":"normal","row":3,"col":9}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        s.step();
        assert!(s.rakes.is_empty());
        assert_eq!(s.zombies[0].status, UnitStatus::Dead);
        assert_eq!(s.events.get("rake_triggered"), Some(&1));
    }

    #[test]
    fn simple_ladder_zombie_places_ladder_on_nut() {
        let text = r#"{"max_frames":1,"plants":[{"type":"wallnut","row":3,"col":1}],"zombies":[{"type":"ladder","row":3,"x":90}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        s.step();
        assert_eq!(s.ladders, vec![GridObject { row: 3, col: 1 }]);
        assert!(!s.zombies[0].tool);
        assert_eq!(s.events.get("ladder_placed"), Some(&1));
    }

    #[test]
    fn simple_zombie_bites_plant_on_fixed_four_tick() {
        let text = r#"{"max_frames":4,"plants":[{"type":"peashooter","row":3,"col":1,"cooldown":150}],"zombies":[{"type":"normal","row":3,"x":90,"hp":270}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        for _ in 0..4 {
            s.step();
        }
        assert_eq!(s.plants[0].hp, 296);
        assert_eq!(s.events.get("plant_bitten"), Some(&1));
    }

    #[test]
    fn simple_spikeweed_pulses_after_windup_and_is_not_bitten() {
        let text = r#"{"max_frames":26,"plants":[{"type":"spikeweed","row":3,"col":2}],"zombies":[{"type":"normal","row":3,"x":100,"speed":0.0}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        for _ in 0..26 {
            s.step();
        }
        assert_eq!(s.plants[0].hp, 300);
        assert_eq!(s.zombies[0].hp, 250);
        assert_eq!(s.events.get("spikeweed_pulse"), Some(&1));
        assert_eq!(s.events.get("plant_bitten"), None);
    }

    #[test]
    fn simple_spikerock_pulses_twice_and_bypasses_screen_door() {
        let text = r#"{"max_frames":70,"plants":[{"type":"spikerock","row":3,"col":2}],"zombies":[{"type":"screen_door","row":3,"x":100,"speed":0.0,"shield_hp":1100}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        for _ in 0..70 {
            s.step();
        }
        assert_eq!(s.plants[0].hp, 450);
        assert_eq!(s.zombies[0].hp, 230);
        assert_eq!(s.zombies[0].shield_hp, 1100);
        assert_eq!(s.events.get("spikerock_pulse"), Some(&2));
        assert_eq!(s.events.get("plant_bitten"), None);
    }

    #[test]
    fn simple_spike_strict_edge_does_not_pulse() {
        let text = r#"{"max_frames":30,"plants":[{"type":"spikeweed","row":3,"col":1}],"zombies":[{"type":"normal","row":3,"x":54,"speed":0.0}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        for _ in 0..30 {
            s.step();
        }
        assert_eq!(s.zombies[0].hp, 270);
        assert_eq!(s.events.get("spikeweed_pulse"), None);
    }

    #[test]
    fn simple_batch_is_seeded_and_sorted_by_run_index() {
        let text = r#"{"seed":9223372036854775807,"runs":4,"max_frames":1,"plants":[],"zombies":[{"type":"normal","row":3,"x":500}],"brains":[3]}"#;
        let scenario = parse_scenario(text).unwrap();
        let batch = run_simple_batch(scenario, 2);
        assert_eq!(batch.runs, 4);
        assert_eq!(batch.parallel_workers, 2);
        assert_eq!(
            batch
                .results
                .iter()
                .map(|row| row.run_index)
                .collect::<Vec<_>>(),
            vec![0, 1, 2, 3]
        );
        assert_eq!(
            batch.results.iter().map(|row| row.seed).collect::<Vec<_>>(),
            vec![i64::MAX, i64::MIN, i64::MIN + 1, i64::MIN + 2]
        );
        assert_eq!(batch.results[0].result.frames, 1);
        assert_eq!(batch.outcomes["undecided"].count, 4);
    }

    #[test]
    fn simple_batch_clamps_workers_and_preserves_single_run_state() {
        let text = r#"{"seed":7,"runs":1,"max_frames":1,"plants":[],"zombies":[{"type":"normal","row":3,"x":500}],"brains":[3]}"#;
        let scenario = parse_scenario(text).unwrap();
        let batch = run_simple_batch(scenario, 99);
        assert_eq!(batch.parallel_workers, 1);
        assert_eq!(batch.results.len(), 1);
        assert_eq!(batch.results[0].seed, 7);
        assert_eq!(batch.results[0].result.winner, "undecided");
    }
}
