#![cfg_attr(
  all(not(debug_assertions), target_os = "windows"),
  windows_subsystem = "windows"
)]

use tauri::api::process::{Command, CommandChild};
use tauri::{Manager, RunEvent};
use std::sync::{Arc, Mutex};

struct SidecarState {
  child: Mutex<Option<CommandChild>>,
}

fn main() {
  tauri::Builder::default()
    .manage(SidecarState {
      child: Mutex::new(None),
    })
    .setup(|app| {
      let handle = app.handle();
      
      // Spawn python server sidecar
      println!("Initializing local AI sidecar binary...");
      match Command::new_sidecar("server") {
        Ok(cmd) => {
          match cmd.spawn() {
            Ok((mut rx, child)) => {
              println!("AI sidecar spawned successfully.");
              
              // Store sidecar reference in app state to manage its lifetime
              let state = handle.state::<SidecarState>();
              *state.child.lock().unwrap() = Some(child);
              
              // Read stdout/stderr from child asynchronously
              tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                  if let tauri::api::process::CommandEvent::Stdout(line) = event {
                    println!("[Sidecar Out]: {}", line);
                  } else if let tauri::api::process::CommandEvent::Stderr(line) = event {
                    eprintln!("[Sidecar Err]: {}", line);
                  }
                }
              });
            }
            Err(e) => {
              eprintln!("CRITICAL: Failed to spawn sidecar: {}", e);
            }
          }
        }
        Err(e) => {
          eprintln!("CRITICAL: Failed to locate sidecar definition: {}", e);
        }
      }
      
      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
