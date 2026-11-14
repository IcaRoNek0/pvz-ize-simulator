use pvz_ize_native_sim::{parse_scenario, run_simple_batch, CoreState, SimpleState};
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
    let max_frames = scenario.max_frames;
    let mode = scenario.mode.clone();
    let args: Vec<String> = std::env::args().collect();
    if args.iter().any(|arg| arg == "--batch") {
        let workers = args
            .windows(2)
            .find(|window| window[0] == "--workers")
            .and_then(|window| window[1].parse::<usize>().ok())
            .unwrap_or_else(|| {
                std::thread::available_parallelism()
                    .map(|n| n.get())
                    .unwrap_or(1)
            });
        let result = run_simple_batch(scenario, workers);
        println!(
            "{}",
            serde_json::to_string(&result).expect("serialize batch result")
        );
    } else if args.iter().any(|arg| arg == "--slice" || arg == "simple") {
        let result = SimpleState::from(scenario).run(max_frames);
        println!(
            "{}",
            serde_json::to_string(&result).expect("serialize result")
        );
    } else {
        let result = CoreState::from(scenario).run_motion(max_frames, &mode);
        println!(
            "{}",
            serde_json::to_string(&result).expect("serialize result")
        );
    }
}
