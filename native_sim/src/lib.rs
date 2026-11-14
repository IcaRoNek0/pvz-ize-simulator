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
        let x = if has_col {
            let c = col(z.get("col"), &format!("zombies[{i}].col"))?;
            40.0 - 30.0 + 80.0 * f64::from(c - 1)
        } else {
            f64_field(z.get("x"), 680.0, &format!("zombies[{i}].x"))?
        };
        let c = ((x - 10.0) / 80.0).floor().clamp(0.0, 8.0) as u8 + 1;
        zombies.push(Zombie {
            id,
            kind: string_field(z.get("type"), "normal", "zombie.type")?,
            row: r,
            col: c,
            x,
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
            let direction = if z.hypnotized { 1.0 } else { -1.0 };
            z.x += direction * z.speed;
            z.age += 1;
            if z.x <= -80.0 {
                z.status = UnitStatus::Exited;
            }
            if z.x <= 20.0 && !z.hypnotized {
                z.status = UnitStatus::EnteredHouse;
            }
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
}
