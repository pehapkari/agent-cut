//! Validation against agent-cut/schema/*.schema.json plus checks a schema
//! can't do (referenced files exist, TODO comments, missing YouTube link).

use crate::model::{Event, Lecture};
use serde_json::{json, Value};
use std::path::Path;

pub const EVENT_SCHEMA: &str = include_str!("../../schema/event.schema.json");
pub const TALK_SCHEMA: &str = include_str!("../../schema/talk.schema.json");
pub const LECTURE_SCHEMA: &str = include_str!("../../schema/lecture.schema.json");

#[derive(Clone, Copy, PartialEq, PartialOrd)]
pub enum Level {
    Warn,
    Error,
}

pub struct Issue {
    pub level: Level,
    pub file: &'static str,
    pub msg: String,
}

impl Issue {
    fn error(file: &'static str, msg: String) -> Self {
        Self { level: Level::Error, file, msg }
    }
    fn warn(file: &'static str, msg: String) -> Self {
        Self { level: Level::Warn, file, msg }
    }
}

/// Schema errors as "key: message" lines.
pub fn schema_errors(schema: &str, instance: &Value) -> Vec<String> {
    let schema: Value = serde_json::from_str(schema).expect("bundled schema is valid JSON");
    let validator = jsonschema::validator_for(&schema).expect("bundled schema compiles");
    validator
        .iter_errors(instance)
        .map(|e| {
            let path = e.instance_path().to_string();
            let key = path.trim_start_matches('/').replace('/', ".");
            if key.is_empty() {
                e.to_string()
            } else {
                format!("{key}: {e}")
            }
        })
        .collect()
}

fn exists(dir: &Path, file: &'static str, key: &str, rel: &str, out: &mut Vec<Issue>) {
    if !rel.is_empty() && !dir.join(rel).exists() {
        out.push(Issue::error(file, format!("{key}: soubor {rel} neexistuje")));
    }
}

pub fn event(e: &Event) -> Vec<Issue> {
    let mut out = Vec::new();
    let Some(fm) = &e.fm else {
        return vec![Issue::error("event.md", "chybí front matter (--- … ---)".into())];
    };
    for m in schema_errors(EVENT_SCHEMA, &fm.to_json()) {
        out.push(Issue::error("event.md", m));
    }
    exists(&e.dir, "event.md", "image", &e.get("image"), &mut out);
    exists(&e.dir, "event.md", "partner.logo", &e.get("partner.logo"), &mut out);
    for t in fm.todos() {
        out.push(Issue::warn("event.md", t));
    }
    out
}

pub fn lecture(l: &Lecture) -> Vec<Issue> {
    let mut out = Vec::new();
    match &l.fm {
        None => out.push(Issue::error("talk.md", "chybí front matter (--- … ---)".into())),
        Some(fm) => {
            for m in schema_errors(TALK_SCHEMA, &fm.to_json()) {
                out.push(Issue::error("talk.md", m));
            }
            exists(&l.dir, "talk.md", "photo", &l.get("photo"), &mut out);
            if l.abstract_text().is_empty() {
                out.push(Issue::warn("talk.md", "chybí anotace (text pod hlavičkou)".into()));
            }
            for t in fm.todos() {
                out.push(Issue::warn("talk.md", t));
            }
        }
    }
    match &l.config {
        None if l.config_file().exists() => out.push(Issue::error("lecture.json", "není platný JSON".into())),
        None => out.push(Issue::warn("lecture.json", "zatím neexistuje (vytvoří krok 1 po nahrání záznamů)".into())),
        Some(cfg) => {
            for m in schema_errors(LECTURE_SCHEMA, cfg) {
                out.push(Issue::error("lecture.json", m));
            }
            for key in ["audio", "screen", "camera"] {
                let files: Vec<&str> = match &cfg[key] {
                    Value::String(s) => vec![s],
                    Value::Array(a) => a.iter().filter_map(|v| v.as_str()).collect(),
                    _ => vec![],
                };
                for f in files {
                    exists(&l.dir, "lecture.json", key, f, &mut out);
                }
            }
        }
    }
    if l.dir.join("out/lecture.fcpxml").exists() && l.get("youtube").is_empty() {
        out.push(Issue::warn("talk.md", "youtube: po nahrání videa doplň odkaz (krok 13)".into()));
    }
    out
}

pub fn to_json(issues: &[Issue]) -> Value {
    issues
        .iter()
        .map(|i| json!({"level": if i.level == Level::Error {"error"} else {"warn"}, "file": i.file, "message": i.msg}))
        .collect()
}
