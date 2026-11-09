//! pk – akce Péhápkařů: přehled, nová akce, nový řečník, úpravy configů.
//! Bez argumentů spustí TUI; stejné operace jdou jako příkazy (pro skripty a agenty).

mod check;
mod edit;
mod fm;
mod model;
mod status;
mod tui;

use anyhow::{bail, Result};
use clap::{Parser, Subcommand};
use serde_json::json;
use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Parser)]
#[command(name = "pk", version, about = "Péhápkaři: akce, řečníci a stav pipeline. Bez příkazu spustí TUI.")]
struct Cli {
    #[command(subcommand)]
    cmd: Option<Cmd>,
}

#[derive(Subcommand)]
enum Cmd {
    /// Přehled akcí, přednášek a stavu kroků pipeline
    Status {
        #[arg(long)]
        json: bool,
    },
    /// Kontrola configů (schéma, odkazované soubory); exit 1 při chybě
    Check {
        #[arg(long)]
        json: bool,
    },
    /// Akce (sraz-XX/event.md)
    Event {
        #[command(subcommand)]
        cmd: EventCmd,
    },
    /// Řečník (sraz-XX/<řečník>/talk.md)
    Speaker {
        #[command(subcommand)]
        cmd: SpeakerCmd,
    },
    /// Hodnota z event.md / talk.md / lecture.json (klíč partner.logo, body = anotace)
    Get { file: PathBuf, key: String },
    /// Změna hodnot: pk set sraz-79/souki/talk.md youtube=https://… order=2
    Set {
        file: PathBuf,
        #[arg(required = true, value_name = "KEY=VALUE")]
        pairs: Vec<String>,
    },
    /// Možnosti pro ilustraci a logo partnera (z resources/)
    Resources,
}

#[derive(Subcommand)]
enum EventCmd {
    /// Založí sraz-<NUMBER>/event.md
    New {
        number: i64,
        #[arg(long)]
        date: String,
        #[arg(long, default_value = "18:00")]
        time: String,
        #[arg(long, default_value = "")]
        venue: String,
        /// soubor ilustrace v resources/bgr/ (název nebo cesta ../resources/bgr/…)
        #[arg(long, default_value = "")]
        image: String,
        /// logo partnera v resources/logo/ (název nebo cesta)
        #[arg(long, default_value = "")]
        partner: String,
        /// jméno partnera (jinak z názvu loga)
        #[arg(long, default_value = "")]
        partner_name: String,
    },
}

#[derive(Subcommand)]
enum SpeakerCmd {
    /// Založí složku řečníka s talk.md (fotka se zkopíruje)
    Add {
        /// akce: 79, sraz-79 nebo cesta
        event: String,
        #[arg(long)]
        name: String,
        #[arg(long)]
        title: String,
        #[arg(long)]
        photo: Option<PathBuf>,
        #[arg(long)]
        order: Option<i64>,
        /// název složky (jinak příjmení bez diakritiky)
        #[arg(long)]
        slug: Option<String>,
        /// anotace
        #[arg(long, default_value = "")]
        r#abstract: String,
    },
}

fn main() -> ExitCode {
    match run() {
        Ok(code) => code,
        Err(e) => {
            eprintln!("chyba: {e:#}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<ExitCode> {
    let cli = Cli::parse();
    let root = model::find_root()?;
    let Some(cmd) = cli.cmd else {
        tui::run(root)?;
        return Ok(ExitCode::SUCCESS);
    };
    match cmd {
        Cmd::Status { json } => status(&root, json)?,
        Cmd::Check { json } => return check(&root, json),
        Cmd::Event { cmd: EventCmd::New { number, date, time, venue, image, partner, partner_name } } => {
            let e = edit::NewEvent {
                number,
                date,
                time,
                venue,
                image: resource(&root, "bgr", &image)?,
                partner_logo: resource(&root, "logo", &partner)?,
                partner_name,
            };
            println!("{}", edit::new_event(&root, &e)?.join("event.md").display());
        }
        Cmd::Speaker { cmd: SpeakerCmd::Add { event, name, title, photo, order, slug, r#abstract } } => {
            let events = model::scan(&root)?;
            let ev = model::find_event(&events, &event)?;
            let s = edit::NewSpeaker { name, title, photo, order, slug, abstract_text: r#abstract };
            println!("{}", edit::add_speaker(ev, &s)?.join("talk.md").display());
        }
        Cmd::Get { file, key } => {
            let value = if model::file_name(&file) == "lecture.json" {
                let v: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(&file)?)?;
                match &v[&key] {
                    serde_json::Value::String(s) => s.clone(),
                    other => other.to_string(),
                }
            } else {
                let fm = model::read_fm(&file).ok_or_else(|| anyhow::anyhow!("chybí front matter"))?;
                if key == "body" { fm.body.trim().to_string() } else { fm.get(&key).unwrap_or_default() }
            };
            println!("{value}");
        }
        Cmd::Set { file, pairs } => {
            for p in pairs {
                let Some((k, v)) = p.split_once('=') else { bail!("očekávám KEY=VALUE, dostal jsem {p}") };
                edit::set(&file, k, v)?;
            }
        }
        Cmd::Resources => {
            for sub in ["bgr", "logo"] {
                println!("{sub}:");
                for o in model::resource_options(&root, sub, &["png", "jpg", "svg"]) {
                    println!("  {o}");
                }
            }
        }
    }
    Ok(ExitCode::SUCCESS)
}

/// Accept a bare file name from resources/<sub>/ or a path as written in event.md.
fn resource(root: &std::path::Path, sub: &str, value: &str) -> Result<String> {
    if value.is_empty() || value.contains('/') {
        return Ok(value.to_string());
    }
    let opts = model::resource_options(root, sub, &["png", "jpg", "svg"]);
    let hits: Vec<&String> = opts.iter().filter(|o| model::file_name(std::path::Path::new(o)).starts_with(value)).collect();
    match hits.as_slice() {
        [one] => Ok(one.to_string()),
        [] => bail!("{value} není v resources/{sub}/ (pk resources)"),
        _ => bail!("{value} odpovídá víc souborům v resources/{sub}/"),
    }
}

fn status(root: &std::path::Path, as_json: bool) -> Result<()> {
    let events = model::scan(root)?;
    if as_json {
        let v: Vec<_> = events
            .iter()
            .map(|e| {
                json!({
                    "id": e.id(), "dir": e.dir, "number": e.number(), "date": e.get("date"),
                    "issues": check::to_json(&check::event(e)),
                    "lectures": e.lectures.iter().map(|l| json!({
                        "id": l.id(), "dir": l.dir, "speaker": l.get("speaker"), "title": l.get("title"),
                        "order": l.order(), "youtube": l.get("youtube"),
                        "steps": status::to_json(&status::steps(l)),
                        "issues": check::to_json(&check::lecture(l)),
                    })).collect::<Vec<_>>(),
                })
            })
            .collect();
        println!("{}", serde_json::to_string_pretty(&v)?);
        return Ok(());
    }
    for e in &events {
        println!("{}  {}. {}  {}", e.id(), e.number(), e.get("name"), e.get("date"));
        for l in &e.lectures {
            let bar: String = status::steps(l)
                .iter()
                .map(|s| match s.state {
                    status::State::Done => '✓',
                    status::State::Stale => '!',
                    status::State::Missing => '·',
                    status::State::Skip => '-',
                })
                .collect();
            println!("  {:<10} {bar}  {} – {}", l.id(), l.get("speaker"), l.get("title"));
        }
    }
    println!("\nkroky 0–13: ✓ hotovo  ! zastaralé  · chybí  - netýká se");
    Ok(())
}

fn check(root: &std::path::Path, as_json: bool) -> Result<ExitCode> {
    let events = model::scan(root)?;
    let mut errors = 0;
    let mut all = Vec::new();
    for e in &events {
        let mut items = vec![(e.id(), check::event(e))];
        items.extend(e.lectures.iter().map(|l| (format!("{}/{}", e.id(), l.id()), check::lecture(l))));
        for (id, issues) in items {
            errors += issues.iter().filter(|i| i.level == check::Level::Error).count();
            if as_json {
                all.push(json!({"id": id, "issues": check::to_json(&issues)}));
            } else {
                for i in issues {
                    let tag = if i.level == check::Level::Error { "chyba" } else { "pozor" };
                    println!("{tag:<6} {id}/{}: {}", i.file, i.msg);
                }
            }
        }
    }
    if as_json {
        println!("{}", serde_json::to_string_pretty(&all)?);
    } else if errors == 0 {
        println!("bez chyb");
    }
    Ok(if errors > 0 { ExitCode::FAILURE } else { ExitCode::SUCCESS })
}
