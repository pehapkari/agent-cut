//! Creating events and speakers and changing single config values.
//! Shared by the CLI and the TUI; every write is validated first.

use crate::check::{schema_errors, EVENT_SCHEMA, LECTURE_SCHEMA, TALK_SCHEMA};
use crate::fm::FrontMatter;
use crate::model::{file_name, read_fm, Event};
use anyhow::{bail, Context, Result};
use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};

pub const EVENT_NAME: &str = "pražský sraz přátel PHP";

pub struct NewEvent {
    pub number: i64,
    pub date: String,
    pub time: String,
    pub venue: String,
    pub image: String,        // relative to the event dir
    pub partner_logo: String, // relative to the event dir
    pub partner_name: String,
}

pub struct NewSpeaker {
    pub name: String,
    pub title: String,
    pub photo: Option<PathBuf>,
    pub order: Option<i64>,
    pub slug: Option<String>,
    pub abstract_text: String,
}

pub fn new_event(root: &Path, e: &NewEvent) -> Result<PathBuf> {
    let dir = root.join(format!("sraz-{}", e.number));
    if dir.exists() {
        bail!("{} už existuje", dir.display());
    }
    let partner = if e.partner_name.is_empty() { partner_name(&e.partner_logo) } else { e.partner_name.clone() };
    let number = e.number.to_string();
    let fm = FrontMatter::new(
        &[
            ("number", &number),
            ("name", EVENT_NAME),
            ("date", &e.date),
            ("time", &e.time),
            ("venue", &e.venue),
            ("url", "pehapkari.cz"),
            ("image", &e.image),
            ("partner.name", &partner),
            ("partner.logo", &e.partner_logo),
        ],
        "Volný popis akce (pozvánka, poznámky).\n",
    );
    validate(EVENT_SCHEMA, &fm.to_json(), &[])?;
    fs::create_dir(&dir)?;
    fs::write(dir.join("event.md"), fm.render())?;
    Ok(dir)
}

pub fn add_speaker(event: &Event, s: &NewSpeaker) -> Result<PathBuf> {
    let slug = s.slug.clone().filter(|x| !x.is_empty()).unwrap_or_else(|| slugify(s.name.split_whitespace().last().unwrap_or("")));
    if slug.is_empty() {
        bail!("chybí jméno řečníka");
    }
    let dir = event.dir.join(&slug);
    if dir.exists() {
        bail!("{} už existuje", dir.display());
    }
    let order = s.order.unwrap_or_else(|| event.lectures.iter().map(|l| l.order()).filter(|&o| o != i64::MAX).max().unwrap_or(0) + 1);
    let photo_name = match &s.photo {
        Some(p) => {
            if !p.is_file() {
                bail!("fotka {} neexistuje", p.display());
            }
            let ext = p.extension().map(|x| x.to_string_lossy().to_lowercase()).unwrap_or_else(|| "jpg".into());
            format!("{slug}.{ext}")
        }
        None => format!("{slug}.jpg"),
    };
    let order_s = order.to_string();
    let body = if s.abstract_text.is_empty() { String::new() } else { format!("{}\n", s.abstract_text.trim()) };
    let fm = FrontMatter::new(
        &[("speaker", &s.name), ("title", &s.title), ("photo", &photo_name), ("order", &order_s)],
        &body,
    );
    validate(TALK_SCHEMA, &fm.to_json(), &[])?;
    fs::create_dir(&dir)?;
    fs::write(dir.join("talk.md"), fm.render())?;
    if let Some(p) = &s.photo {
        fs::copy(p, dir.join(&photo_name)).context("kopie fotky")?; // copy: the original stays untouched
    }
    Ok(dir)
}

/// Set one value in event.md, talk.md (key "body" = text under the header) or lecture.json.
/// Refuses the change when it adds a schema error.
pub fn set(file: &Path, key: &str, value: &str) -> Result<()> {
    let text = fs::read_to_string(file).with_context(|| format!("čtení {}", file.display()))?;
    match file_name(file).as_str() {
        "lecture.json" => {
            let mut cfg: Value = serde_json::from_str(&text).context("lecture.json není platný JSON")?;
            let before = schema_errors(LECTURE_SCHEMA, &cfg);
            // JSON literal (null, 3, ["a","b"]) when it parses, otherwise a plain string
            let v = serde_json::from_str(value).unwrap_or_else(|_| Value::String(value.to_string()));
            cfg.as_object_mut().context("lecture.json není objekt")?.insert(key.to_string(), v);
            validate(LECTURE_SCHEMA, &cfg, &before)?;
            fs::write(file, serde_json::to_string_pretty(&cfg)? + "\n")?;
        }
        name @ ("event.md" | "talk.md") => {
            let schema = if name == "event.md" { EVENT_SCHEMA } else { TALK_SCHEMA };
            let mut fm = read_fm(file).context("chybí front matter")?;
            let before = schema_errors(schema, &fm.to_json());
            if key == "body" {
                fm.body = format!("{}\n", value.trim());
            } else {
                fm.set(key, value);
            }
            validate(schema, &fm.to_json(), &before)?;
            fs::write(file, fm.render())?;
        }
        _ => bail!("neznámý soubor {} (event.md, talk.md, lecture.json)", file.display()),
    }
    Ok(())
}

fn validate(schema: &str, v: &Value, allowed: &[String]) -> Result<()> {
    let new: Vec<String> = schema_errors(schema, v).into_iter().filter(|e| !allowed.contains(e)).collect();
    if !new.is_empty() {
        bail!("neplatná hodnota: {}", new.join("; "));
    }
    Ok(())
}

/// "Logo Alma Career.svg" → "Alma Career", "simplia.svg" → "Simplia".
pub fn partner_name(logo: &str) -> String {
    let stem = Path::new(logo).file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_default();
    let stem = stem.strip_prefix("Logo ").unwrap_or(&stem);
    let mut c = stem.chars();
    c.next().map(|f| f.to_uppercase().collect::<String>() + c.as_str()).unwrap_or_default()
}

/// Folder name from a surname: lowercase ASCII, "Matějka" → "matejka".
pub fn slugify(s: &str) -> String {
    const FROM: &str = "áäčďéěëíĺľňóôöŕřšťúůüýžÁÄČĎÉĚËÍĹĽŇÓÔÖŔŘŠŤÚŮÜÝŽ";
    const TO: &str = "aacdeeeillnooorrstuuuyzAACDEEEILLNOOORRSTUUUYZ";
    s.chars()
        .map(|c| FROM.chars().position(|f| f == c).and_then(|i| TO.chars().nth(i)).unwrap_or(c))
        .map(|c| c.to_ascii_lowercase())
        .map(|c| if c.is_ascii_alphanumeric() { c } else { '-' })
        .collect::<String>()
        .trim_matches('-')
        .to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn names() {
        assert_eq!(slugify("Matějka"), "matejka");
        assert_eq!(slugify("Šťastný"), "stastny");
        assert_eq!(partner_name("../resources/logo/Logo Alma Career.svg"), "Alma Career");
        assert_eq!(partner_name("../resources/logo/simplia.svg"), "Simplia");
    }
}
