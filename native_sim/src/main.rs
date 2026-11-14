use pvz_ize_native_sim::{parse_scenario, CoreState};
use std::io::{self, Read};
fn main() {
    let mut input = String::new();
    if let Err(error) = io::stdin().read_to_string(&mut input) {
        eprintln!("read input: {error}");
        std::process::exit(2);
    }
    let scenario = match parse_scenario(&input) {
        Ok(value) => value,
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(2);
        }
    };
    let state = CoreState::from(scenario);
    println!(
        "{}",
        serde_json::to_string(&state).expect("serialize state")
    );
}
