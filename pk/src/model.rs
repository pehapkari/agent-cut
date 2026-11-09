//! Events (sraz-XX/event.md) and their lectures (<řečník>/talk.md + lecture.json).

use crate::fm::FrontMatter;
use anyhow::{bail, Context, Result};
use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};

pub struct Event {
    pub dir: PathBuf,
    pub fm: Option<FrontMatter>,
    pub lectures: Vec<Lecture>,
}

pub struct Lecture {
    pub dir: PathBuf,
    pub fm: Option<FrontMatter>,
    pub config: Option<Value>,
}

impl Event {
    pub fn id(&self) -> String {
        file_name(&self.dir)
    }
    pub fn file(&self) -> PathBuf {
        self.dir.join("event.md")
    }
    pub fn number(&self) -> i64 {
        self.fm.as_ref().and_then(|f| f.get("number")).and_then(|n| n.parse().ok()).unwrap_or(0)
    }
    pub fn get(&self, key: &str) -> String {
        self.fm.as_ref().and_then(|f| f.get(key)).unwrap_or_default()
    }
}

impl Lecture {
    pub fn id(&self) -> String {
        file_name(&self.dir)
    }
    pub fn file(&self) -> PathBuf {
        self.dir.join("talk.md")
    }
    pub fn config_file(&self) -> PathBuf {
        self.dir.join("lecture.json")
    }
    pub fn get(&self, key: &str) -> String {
        self.fm.as_ref().and_then(|f| f.get(key)).unwrap_or_default()
    }
    pub fn order(&self) -> i64 {
        self.get("order").parse().unwrap_or(i64::MAX)
    }
    pub fn abstract_text(&self) -> String {
        self.fm.as_ref().map(|f| f.body.trim().to_string()).unwrap_or_default()
    }
}

pub fn file_name(p: &Path) -> String {
    p.file_name().map(|s| s.to_string_lossy().into_owned()).unwrap_or_default()
}

/// pehapkari/ = the directory that contains agent-cut/ (PK_ROOT overrides).
pub fn find_root() -> Result<PathBuf> {
    if let Ok(r) = std::env::var("PK_ROOT") {
        return Ok(PathBuf::from(r));
    }
    let starts = [std::env::current_dir().ok(), std::env::current_exe().ok()];
    for start in starts.into_iter().flatten() {
        for dir in start.ancestors() {
            if dir.join("agent-cut").is_dir() {
                return Ok(dir.to_path_buf());
            }
        }
    }
    bail!("složka s agent-cut/ nenalezena – spusť pk uvnitř pehapkari/ nebo nastav PK_ROOT")
}

/// Shared assets: resources/ (or resources-poc/ until renamed).
pub fn resources(root: &Path) -> PathBuf {
    let r = root.join("resources");
    if r.is_dir() {
        r
    } else {
        root.join("resources-poc")
    }
}

pub fn read_fm(path: &Path) -> Option<FrontMatter> {
    FrontMatter::parse(&fs::read_to_string(path).ok()?)
}

pub fn scan(root: &Path) -> Result<Vec<Event>> {
    let mut events = Vec::new();
    for dir in subdirs(root)? {
        let file = dir.join("event.md");
        if !file.is_file() {
            continue;
        }
        let mut lectures: Vec<Lecture> = subdirs(&dir)?
            .into_iter()
            .filter(|d| d.join("talk.md").is_file())
            .map(|d| Lecture {
                fm: read_fm(&d.join("talk.md")),
                config: fs::read_to_string(d.join("lecture.json")).ok().and_then(|t| serde_json::from_str(&t).ok()),
                dir: d,
            })
            .collect();
        lectures.sort_by_key(|l| (l.order(), l.id()));
        events.push(Event { fm: read_fm(&file), dir, lectures });
    }
    events.sort_by_key(|e| std::cmp::Reverse(e.number()));
    Ok(events)
}

/// Real subdirectories (symlinks like pehapkari/souki → sraz-79/souki are skipped).
fn subdirs(dir: &Path) -> Result<Vec<PathBuf>> {
    let mut out = Vec::new();
    for e in fs::read_dir(dir).with_context(|| format!("čtení {}", dir.display()))? {
        let e = e?;
        let name = e.file_name();
        if e.file_type()?.is_dir() && !name.to_string_lossy().starts_with('.') {
            out.push(e.path());
        }
    }
    out.sort();
    Ok(out)
}

/// Find an event by "79", "sraz-79" or a path.
pub fn find_event<'a>(events: &'a [Event], name: &str) -> Result<&'a Event> {
    events
        .iter()
        .find(|e| e.id() == name || e.number().to_string() == name || e.dir == Path::new(name))
        .with_context(|| format!("akce {name} nenalezena"))
}

/// Files in resources/<sub>/ as paths relative to an event dir (../resources/…).
pub fn resource_options(root: &Path, sub: &str, ext: &[&str]) -> Vec<String> {
    let res = resources(root);
    let mut out: Vec<String> = fs::read_dir(res.join(sub))
        .into_iter()
        .flatten()
        .flatten()
        .map(|e| e.path())
        .filter(|p| p.extension().is_some_and(|x| ext.contains(&x.to_string_lossy().to_lowercase().as_str())))
        .map(|p| format!("../{}/{sub}/{}", file_name(&res), file_name(&p)))
        .collect();
    out.sort();
    out
}
