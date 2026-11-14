//! Rust-side foundation for the pvz-ize Simulator migration.
//!
//! This crate deliberately starts with input normalization and a deterministic
//! frame/state boundary.  The Python Simulator remains the fidelity reference
//! until each behavior is ported and covered by differential tests.

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
        plants.push(Plant {
            id,
            kind: string_field(p.get("type"), "peashooter", "plant.type")?,
            row: r,
            col: c,
            hp: i64_field(p.get("hp"), 300, "plant.hp")? as i32,
            cooldown: u64_field(p.get("cooldown"), 0, "plant.cooldown")? as u32,
            state_timer: u64_field(p.get("state_timer"), 0, "plant.state_timer")? as u32,
            layer: string_field(p.get("layer"), "main", "plant.layer")?,
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
        zombies.push(Zombie {
            id,
            kind,
            row: r,
            col: c,
            x,
            x_fp: (x * 1000.0).round() as i64,
            speed_fp: (f64_field(z.get("speed"), 0.143, "zombie.speed")? * 1000.0).round() as i64,
            hp: i64_field(z.get("hp"), 270, "zombie.hp")? as i32,
            helmet_hp: i64_field(z.get("helmet_hp"), 0, "zombie.helmet_hp")? as i32,
            shield_hp: i64_field(z.get("shield_hp"), 0, "zombie.shield_hp")? as i32,
            speed: f64_field(z.get("speed"), 0.143, "zombie.speed")?,
            age: u64_field(z.get("age"), 0, "zombie.age")?,
            chilled: u64_field(z.get("chilled"), 0, "zombie.chilled")? as u32,
            headless: bool_field(z.get("headless"), false, "zombie.headless")?,
            hypnotized: bool_field(z.get("hypnotized"), false, "zombie.hypnotized")?,
            tool: bool_field(z.get("tool"), true, "zombie.tool")?,
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
    pub x: f64,
    #[serde(skip)]
    pub x_fp: i64,
    pub damage: i32,
    pub active: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct SimpleState {
    pub frame: u64,
    pub plants: Vec<Plant>,
    pub zombies: Vec<Zombie>,
    pub brains: Vec<Brain>,
    pub projectiles: Vec<SimpleProjectile>,
    pub events: std::collections::BTreeMap<String, u64>,
}

impl From<Scenario> for SimpleState {
    fn from(s: Scenario) -> Self {
        Self {
            frame: 0,
            plants: s.plants,
            zombies: s.zombies,
            brains: s.brains,
            projectiles: Vec::new(),
            events: std::collections::BTreeMap::new(),
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

fn plant_x_fp(col: u8) -> i64 {
    40_000 + 80_000 * i64::from(col.saturating_sub(1))
}

impl SimpleState {
    fn terminal(&self) -> Option<(String, String)> {
        if self.brains.iter().all(|b| b.hp <= 0) {
            return Some(("zombies".into(), "all_brains_eaten".into()));
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
        let mut fired = 0_u64;
        for p in &mut self.plants {
            if p.hp <= 0 || p.kind != "peashooter" {
                continue;
            }
            if p.cooldown > 0 {
                p.cooldown -= 1;
            }
            if p.cooldown == 0 {
                self.projectiles.push(SimpleProjectile {
                    row: p.row,
                    x: p.x() + 50.0,
                    x_fp: plant_x_fp(p.col) + 50_000,
                    damage: 20,
                    active: true,
                });
                p.cooldown = 150;
                fired += 1;
            }
        }
        for q in &mut self.projectiles {
            if q.active {
                q.x_fp += 8_000;
                q.x = q.x_fp as f64 / 1000.0;
            }
        }
        let mut hits = 0_u64;
        let mut deaths = 0_u64;
        for qi in 0..self.projectiles.len() {
            if !self.projectiles[qi].active {
                continue;
            }
            let (row, x_fp, damage) = (
                self.projectiles[qi].row,
                self.projectiles[qi].x_fp,
                self.projectiles[qi].damage,
            );
            if let Some(z) = self.zombies.iter_mut().find(|z| {
                z.status == UnitStatus::Active
                    && z.hp > 0
                    && z.row == row
                    && (z.x_fp - x_fp).abs() <= 25_000
            }) {
                z.hp = (z.hp - damage).max(0);
                self.projectiles[qi].active = false;
                hits += 1;
                if z.hp == 0 {
                    z.status = UnitStatus::Dead;
                    deaths += 1;
                }
            }
        }
        self.projectiles.retain(|q| q.active && q.x < 900.0);
        let mut bites = 0_u64;
        let mut brain_eaten = 0_u64;
        for zi in 0..self.zombies.len() {
            if self.zombies[zi].status != UnitStatus::Active
                || self.zombies[zi].hp <= 0
                || self.zombies[zi].hypnotized
            {
                continue;
            }
            self.zombies[zi].age += 1;
            let zx_fp = self.zombies[zi].x_fp;
            let row = self.zombies[zi].row;
            let target = self
                .plants
                .iter()
                .enumerate()
                .find(|(_, p)| {
                    let px_fp = plant_x_fp(p.col);
                    p.hp > 0 && p.row == row && zx_fp >= px_fp && zx_fp - px_fp <= 60_000
                })
                .map(|(i, _)| i);
            if let Some(pi) = target {
                if self.zombies[zi].age % 4 == 0 {
                    self.plants[pi].hp = (self.plants[pi].hp - 4).max(0);
                    bites += 1;
                }
            } else {
                self.zombies[zi].x_fp -= self.zombies[zi].speed_fp;
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
        for (name, count) in [
            ("projectile_fired", fired),
            ("projectile_hit", hits),
            ("zombie_died", deaths),
            ("plant_bitten", bites),
            ("brain_eaten", brain_eaten),
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
    fn simple_zombie_bites_plant_on_fixed_four_tick() {
        let text = r#"{"max_frames":4,"plants":[{"type":"peashooter","row":3,"col":1,"cooldown":150}],"zombies":[{"type":"normal","row":3,"x":90,"hp":270}],"brains":[3]}"#;
        let mut s = SimpleState::from(parse_scenario(text).unwrap());
        for _ in 0..4 {
            s.step();
        }
        assert_eq!(s.plants[0].hp, 296);
        assert_eq!(s.events.get("plant_bitten"), Some(&1));
    }
}
