use std::sync::mpsc;
use std::thread;

enum TtsCommand {
    Speak(String),
    Stop,
    Shutdown,
}

pub struct TtsHandle {
    tx: Option<mpsc::Sender<TtsCommand>>,
}

impl TtsHandle {
    pub fn new() -> Self {
        let (tx, rx) = mpsc::channel::<TtsCommand>();

        thread::spawn(move || {
            let mut engine = match tts::Tts::default() {
                Ok(e) => e,
                Err(err) => {
                    eprintln!("TTS init failed: {err}");
                    return;
                }
            };

            let _ = engine.set_volume(0.9);

            while let Ok(cmd) = rx.recv() {
                match cmd {
                    TtsCommand::Speak(text) => {
                        let _ = engine.stop();
                        let _ = engine.speak(text, false);
                    }
                    TtsCommand::Stop => {
                        let _ = engine.stop();
                    }
                    TtsCommand::Shutdown => break,
                }
            }
        });

        TtsHandle { tx: Some(tx) }
    }

    pub fn speak(&self, text: &str) {
        if text.trim().is_empty() {
            return;
        }
        if let Some(tx) = &self.tx {
            let _ = tx.send(TtsCommand::Speak(text.to_string()));
        }
    }

    pub fn stop(&self) {
        if let Some(tx) = &self.tx {
            let _ = tx.send(TtsCommand::Stop);
        }
    }
}

impl Drop for TtsHandle {
    fn drop(&mut self) {
        if let Some(tx) = self.tx.take() {
            let _ = tx.send(TtsCommand::Shutdown);
        }
    }
}
