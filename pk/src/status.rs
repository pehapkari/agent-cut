//! Pipeline progress of a lecture, read from work/ and out/ (nothing is run).

use crate::model::Lecture;
use serde_json::{json, Value};
use std::fs;
use std::path::Path;
use std::time::{Duration, SystemTime};

const SLACK: Duration = Duration::from_secs(60);

#[derive(Clone, Copy, PartialEq)]
pub enum State {
    Done,
    Stale,
    Missing,
    Skip,
}

impl State {
    pub fn as_str(self) -> &'static str {
        match self {
            State::Done => "done",
            State::Stale => "stale",
            State::Missing => "missing",
            State::Skip => "skip",
        }
    }
}

pub struct Step {
    pub id: &'static str,
    pub name: &'static str,
    pub state: State,
    pub note: String,
}

/// (id, name, outputs, inputs) – paths relative to the lecture dir; `dir/*.ext`
/// means every such file in dir. Stale = an editorial input is newer than the
/// newest output. Only inputs a person edits are listed: the pipeline rewrites
/// some of its own files (highlights.json, video-background) and would flag noise.
const STEPS: &[(&str, &str, &[&str], &[&str])] = &[
    ("0", "join", &["work/joined"], &[]),
    ("1", "probe", &["work/probe.json"], &[]),
    ("2", "proxy", &["work/proxy/camera.mp4"], &[]),
    ("3", "audio", &["work/audio_clean.wav"], &[]),
    ("4", "sync", &["work/offsets.json"], &[]),
    ("5", "přepis", &["work/transcript.json"], &[]),
    ("6", "střih", &["out/lecture.fcpxml"], &["work/edit_manual.json", "work/edit_plan.json"]),
    ("7", "highlights", &["work/highlights.md"], &[]),
    ("8", "reels", &["out/reels/*.mp4"], &["work/highlights.json", "work/subs_fixes.json"]),
    ("9", "kontrola", &["work/check/report.md"], &["out/reels/*.mp4"]),
    ("10", "layout", &["work/layout/program.mp4"], &[]),
    ("11", "grafika", &["work/brand/intro.mp4"], &["../event.md", "work/teaser.json"]),
    ("12", "youtube", &["out/youtube.md"], &["work/youtube.json"]),
    ("13", "publikace", &["out/social.html", "out/article.md"], &["work/social.json", "work/article.json", "talk.md"]),
];

pub fn steps(l: &Lecture) -> Vec<Step> {
    let split = |k: &str| l.config.as_ref().is_some_and(|c| c[k].is_array());
    STEPS
        .iter()
        .map(|&(id, name, outputs, inputs)| {
            if id == "0" && !split("audio") && !split("screen") && !split("camera") {
                return Step { id, name, state: State::Skip, note: "nahrávky nejsou rozdělené".into() };
            }
            let outs: Vec<Vec<SystemTime>> = outputs.iter().map(|p| mtimes(&l.dir, p)).collect();
            if outs.iter().any(|o| o.is_empty()) {
                return Step { id, name, state: State::Missing, note: String::new() };
            }
            let newest_out = outs.iter().flatten().max().copied();
            let newest_in = inputs.iter().flat_map(|p| mtimes(&l.dir, p)).max();
            let mut note = String::new();
            if id == "8" {
                note = format!("{} reels", outs[0].len());
            }
            let state = match (newest_in, newest_out) {
                (Some(i), Some(o)) if i > o + SLACK => {
                    note = "vstup je novější než výstup".into();
                    State::Stale
                }
                _ => State::Done,
            };
            Step { id, name, state, note }
        })
        .collect()
}

fn mtimes(dir: &Path, rel: &str) -> Vec<SystemTime> {
    let mtime = |p: &Path| fs::metadata(p).and_then(|m| m.modified()).ok();
    match rel.split_once("/*.") {
        Some((sub, ext)) => fs::read_dir(dir.join(sub))
            .into_iter()
            .flatten()
            .flatten()
            .map(|e| e.path())
            .filter(|p| p.extension().is_some_and(|x| x == ext))
            .filter_map(|p| mtime(&p))
            .collect(),
        None => mtime(&dir.join(rel)).into_iter().collect(),
    }
}

pub fn to_json(steps: &[Step]) -> Value {
    steps.iter().map(|s| json!({"step": s.id, "name": s.name, "state": s.state.as_str(), "note": s.note})).collect()
}
