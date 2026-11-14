use serde_json::{json, Value};
use std::env;
use std::io::{self, BufRead, BufReader, Read, Write};
use std::process::{Command, Stdio};
use std::sync::mpsc;
use std::thread;

struct Task {
    index: usize,
    scenario: Value,
}

fn arg_value(args: &[String], name: &str) -> Option<String> {
    args.windows(2).find(|w| w[0] == name).map(|w| w[1].clone())
}

fn worker_loop(
    rx: mpsc::Receiver<Task>,
    tx: mpsc::Sender<Result<(usize, Value), String>>,
    python: String,
) {
    let child_result = Command::new(&python)
        .args(["-m", "pvz_ize.native_worker"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn();
    let mut child = match child_result {
        Ok(child) => child,
        Err(err) => {
            let _ = tx.send(Err(format!("failed to start Python worker: {err}")));
            return;
        }
    };
    let mut stdin = child.stdin.take().expect("worker stdin");
    let stdout = child.stdout.take().expect("worker stdout");
    let mut reader = BufReader::new(stdout);
    for task in rx {
        let request = json!({"scenario": task.scenario, "index": task.index});
        let line = match serde_json::to_string(&request) {
            Ok(line) => line,
            Err(err) => {
                let _ = tx.send(Err(format!("encode task {}: {err}", task.index)));
                break;
            }
        };
        if let Err(err) = writeln!(stdin, "{line}").and_then(|_| stdin.flush()) {
            let _ = tx.send(Err(format!("write task {}: {err}", task.index)));
            break;
        }
        let mut response = String::new();
        match reader.read_line(&mut response) {
            Ok(0) => {
                let _ = tx.send(Err(format!(
                    "Python worker exited while processing task {}",
                    task.index
                )));
                break;
            }
            Ok(_) => match serde_json::from_str::<Value>(response.trim()) {
                Ok(value) => {
                    if let Some(error) = value.get("error").and_then(Value::as_str) {
                        let _ = tx.send(Err(format!("task {}: {error}", task.index)));
                        break;
                    }
                    let _ = tx.send(Ok((task.index, value)));
                }
                Err(err) => {
                    let _ = tx.send(Err(format!("decode task {} response: {err}", task.index)));
                    break;
                }
            },
            Err(err) => {
                let _ = tx.send(Err(format!("read task {} response: {err}", task.index)));
                break;
            }
        }
    }
    let _ = child.kill();
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let workers = arg_value(&args, "--workers")
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(2)
        .max(1);
    let python = arg_value(&args, "--python").unwrap_or_else(|| "python3".to_string());
    let mut input = String::new();
    if let Err(err) = io::stdin().read_to_string(&mut input) {
        eprintln!("read input: {err}");
        std::process::exit(2);
    }
    let scenario: Value = match serde_json::from_str(&input) {
        Ok(value) => value,
        Err(err) => {
            eprintln!("invalid scenario JSON: {err}");
            std::process::exit(2);
        }
    };
    let runs = scenario.get("runs").and_then(Value::as_u64).unwrap_or(1) as usize;
    if runs == 0 {
        eprintln!("scenario runs must be positive");
        std::process::exit(2);
    }
    let worker_count = workers.min(runs);
    let (result_tx, result_rx) = mpsc::channel();
    let mut task_senders = Vec::with_capacity(worker_count);
    let mut handles = Vec::with_capacity(worker_count);
    for _ in 0..worker_count {
        let (task_tx, task_rx) = mpsc::channel();
        task_senders.push(task_tx);
        let tx = result_tx.clone();
        let py = python.clone();
        handles.push(thread::spawn(move || worker_loop(task_rx, tx, py)));
    }
    drop(result_tx);
    for index in 0..runs {
        let sender = &task_senders[index % worker_count];
        if sender
            .send(Task {
                index,
                scenario: scenario.clone(),
            })
            .is_err()
        {
            eprintln!("worker task channel closed");
            std::process::exit(3);
        }
    }
    drop(task_senders);
    let mut results = Vec::with_capacity(runs);
    for _ in 0..runs {
        match result_rx.recv() {
            Ok(Ok((index, value))) => results.push(json!({"index": index, "payload": value})),
            Ok(Err(err)) => {
                eprintln!("{err}");
                for handle in handles {
                    let _ = handle.join();
                }
                std::process::exit(3);
            }
            Err(err) => {
                eprintln!("collect worker result: {err}");
                std::process::exit(3);
            }
        }
    }
    for handle in handles {
        let _ = handle.join();
    }
    results.sort_by_key(|value| value.get("index").and_then(Value::as_u64).unwrap_or(0));
    let output = json!({"parallel_workers": worker_count, "results": results});
    println!(
        "{}",
        serde_json::to_string(&output).expect("serialize output")
    );
}
