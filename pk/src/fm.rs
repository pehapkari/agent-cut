//! Minimal YAML front matter editor for event.md / talk.md.
//!
//! Full YAML libraries drop comments (`# TODO: ověřit`) and reorder keys on
//! save, so edits here touch only the line of the changed key. Supported is
//! what the files use: scalars and one level of nesting (`partner.logo`).

use serde_json::{Map, Value};

pub struct FrontMatter {
    lines: Vec<String>,
    pub body: String,
}

struct Entry {
    line: usize,
    indent: usize,
    key: String,
    raw: String,
    comment: Option<(usize, String)>, // column of '#', comment text
}

impl FrontMatter {
    pub fn parse(text: &str) -> Option<Self> {
        let mut lines = Vec::new();
        let mut pos = 0;
        for (i, l) in text.split_inclusive('\n').enumerate() {
            pos += l.len();
            let t = l.trim_end_matches(['\n', '\r']);
            if i == 0 {
                if t != "---" {
                    return None;
                }
            } else if t == "---" {
                return Some(Self { lines, body: text[pos..].to_string() });
            } else {
                lines.push(t.to_string());
            }
        }
        None
    }

    pub fn new(pairs: &[(&str, &str)], body: &str) -> Self {
        let mut fm = Self { lines: Vec::new(), body: body.to_string() };
        for (k, v) in pairs {
            fm.set(k, v);
        }
        fm
    }

    pub fn render(&self) -> String {
        let mut s = String::from("---\n");
        for l in &self.lines {
            s.push_str(l);
            s.push('\n');
        }
        s.push_str("---\n");
        s.push_str(&self.body);
        s
    }

    fn entries(&self) -> Vec<Entry> {
        let mut out = Vec::new();
        let mut parent: Option<String> = None;
        for (i, l) in self.lines.iter().enumerate() {
            let t = l.trim_start();
            let indent = l.len() - t.len();
            if t.is_empty() || t.starts_with('#') {
                continue;
            }
            let Some((k, rest)) = t.split_once(':') else { continue };
            if k.is_empty() || !k.chars().all(|c| c.is_alphanumeric() || c == '_' || c == '-') {
                continue;
            }
            let (raw, comment) = split_comment(rest);
            let comment = comment.map(|(c, text)| (indent + k.len() + 1 + c, text));
            let key = if indent == 0 {
                parent = raw.is_empty().then(|| k.to_string());
                k.to_string()
            } else {
                match &parent {
                    Some(p) => format!("{p}.{k}"),
                    None => continue,
                }
            };
            out.push(Entry { line: i, indent, key, raw, comment });
        }
        out
    }

    pub fn get(&self, key: &str) -> Option<String> {
        self.entries().into_iter().find(|e| e.key == key).map(|e| unquote(&e.raw)).filter(|v| !v.is_empty())
    }

    /// Comments containing TODO (unverified values).
    pub fn todos(&self) -> Vec<String> {
        self.entries()
            .into_iter()
            .filter_map(|e| e.comment.filter(|(_, c)| c.contains("TODO")).map(|(_, c)| format!("{}: {}", e.key, c)))
            .collect()
    }

    pub fn set(&mut self, key: &str, value: &str) {
        let entries = self.entries();
        let leaf = key.rsplit('.').next().unwrap_or(key);
        if let Some(e) = entries.iter().find(|e| e.key == key) {
            let mut line = format!("{}{leaf}: {}", " ".repeat(e.indent), yaml_scalar(value));
            if let Some((col, text)) = &e.comment {
                let pad = col.saturating_sub(line.chars().count()).max(2);
                line.push_str(&" ".repeat(pad));
                line.push_str(text);
            }
            self.lines[e.line] = line;
            return;
        }
        match key.split_once('.') {
            None => self.lines.push(format!("{key}: {}", yaml_scalar(value))),
            Some((parent, child)) => {
                let prefix = format!("{parent}.");
                let last = entries.iter().filter(|e| e.key == parent || e.key.starts_with(&prefix)).map(|e| e.line).max();
                let line = format!("  {child}: {}", yaml_scalar(value));
                match last {
                    Some(i) => self.lines.insert(i + 1, line),
                    None => {
                        self.lines.push(format!("{parent}:"));
                        self.lines.push(line);
                    }
                }
            }
        }
    }

    /// Typed view for schema validation (numbers, booleans, nested objects).
    pub fn to_json(&self) -> Value {
        let mut root = Map::new();
        for e in self.entries() {
            if e.raw.is_empty() {
                continue;
            }
            let v = scalar_value(&e.raw);
            match e.key.split_once('.') {
                None => {
                    root.insert(e.key, v);
                }
                Some((p, c)) => {
                    let obj = root.entry(p).or_insert_with(|| Value::Object(Map::new()));
                    if let Value::Object(m) = obj {
                        m.insert(c.to_string(), v);
                    }
                }
            }
        }
        // parents without children still count as present
        for e in self.entries() {
            if e.indent == 0 && e.raw.is_empty() {
                root.entry(e.key).or_insert_with(|| Value::Object(Map::new()));
            }
        }
        Value::Object(root)
    }
}

/// Split `  value  # comment` into the trimmed value and (offset of '#', comment).
fn split_comment(rest: &str) -> (String, Option<(usize, String)>) {
    let mut quote: Option<char> = None;
    let mut prev_space = true;
    for (i, c) in rest.char_indices() {
        match (quote, c) {
            (None, '"' | '\'') => quote = Some(c),
            (Some(q), _) if c == q => quote = None,
            (None, '#') if prev_space => {
                let col = rest[..i].chars().count();
                return (rest[..i].trim().to_string(), Some((col, rest[i..].to_string())));
            }
            _ => {}
        }
        prev_space = c.is_whitespace();
    }
    (rest.trim().to_string(), None)
}

fn unquote(raw: &str) -> String {
    if raw.len() >= 2 && raw.starts_with('"') && raw.ends_with('"') {
        raw[1..raw.len() - 1].replace("\\\"", "\"").replace("\\\\", "\\")
    } else if raw.len() >= 2 && raw.starts_with('\'') && raw.ends_with('\'') {
        raw[1..raw.len() - 1].replace("''", "'")
    } else {
        raw.to_string()
    }
}

fn scalar_value(raw: &str) -> Value {
    if raw.starts_with('"') || raw.starts_with('\'') {
        return Value::String(unquote(raw));
    }
    if let Ok(n) = raw.parse::<i64>() {
        return Value::from(n);
    }
    match raw {
        "true" => Value::Bool(true),
        "false" => Value::Bool(false),
        "null" | "~" => Value::Null,
        _ => Value::String(raw.to_string()),
    }
}

/// Plain scalar when YAML reads it back as the same string (or integer), else quoted.
fn yaml_scalar(v: &str) -> String {
    if v.parse::<i64>().is_ok() {
        return v.to_string();
    }
    let lower = v.to_lowercase();
    let sexagesimal = v.contains(':') && v.split(':').all(|p| !p.is_empty() && p.chars().all(|c| c.is_ascii_digit()));
    let needs_quotes = v.is_empty()
        || v.trim() != v
        || v.starts_with(|c: char| "!&*[]{}|>'\"%@`#,?:-".contains(c))
        || v.contains(": ")
        || v.contains(" #")
        || v.ends_with(':')
        || sexagesimal
        || v.parse::<f64>().is_ok()
        || matches!(lower.as_str(), "true" | "false" | "yes" | "no" | "on" | "off" | "null" | "~");
    if needs_quotes {
        format!("\"{}\"", v.replace('\\', "\\\\").replace('"', "\\\""))
    } else {
        v.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const EVENT: &str = "---\nnumber: 79\nname: pražský sraz\ntime: \"18:00\"          # TODO: ověřit\npartner:\n  name: Simplia\n  logo: ../x.svg\n---\nBody\n";

    #[test]
    fn reads_and_keeps_comments() {
        let mut fm = FrontMatter::parse(EVENT).unwrap();
        assert_eq!(fm.get("time").as_deref(), Some("18:00"));
        assert_eq!(fm.get("partner.logo").as_deref(), Some("../x.svg"));
        assert_eq!(fm.todos().len(), 1);
        fm.set("time", "19:00");
        fm.set("partner.name", "Kosik");
        fm.set("venue", "Impact Hub");
        let out = fm.render();
        assert!(out.contains("time: \"19:00\"          # TODO: ověřit\n"));
        assert!(out.contains("  name: Kosik\n"));
        assert!(out.ends_with("venue: Impact Hub\n---\nBody\n"));
        assert_eq!(fm.to_json()["number"], 79);
        assert_eq!(fm.to_json()["partner"]["logo"], "../x.svg");
    }

    #[test]
    fn quotes_when_needed() {
        assert_eq!(yaml_scalar("Real-time: sync"), "\"Real-time: sync\"");
        assert_eq!(yaml_scalar("https://youtu.be/x"), "https://youtu.be/x");
        assert_eq!(yaml_scalar("2026-09-30"), "2026-09-30");
        assert_eq!(yaml_scalar("Jev (System One)"), "Jev (System One)");
    }
}
