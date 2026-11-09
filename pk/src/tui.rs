//! Interactive overview: events and lectures on the left, details, pipeline
//! steps and issues on the right; forms for new event / speaker and field edits.

use crate::check::{self, Issue, Level};
use crate::edit::{self, NewEvent, NewSpeaker};
use crate::model::{self, Event, Lecture};
use crate::status::{self, State};
use anyhow::Result;
use crossterm::event::{self, Event as TermEvent, KeyCode, KeyEvent, KeyEventKind, KeyModifiers};
use ratatui::layout::{Constraint, Layout, Rect};
use ratatui::style::{Color, Modifier, Style, Stylize};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Clear, List, ListItem, ListState, Paragraph, Wrap};
use ratatui::{DefaultTerminal, Frame};
use std::path::{Path, PathBuf};
use std::process::Command;

const PURPLE: Color = Color::Rgb(0x8b, 0x5c, 0xf6);

#[derive(Clone, Copy)]
enum Item {
    Event(usize),
    Lecture(usize, usize),
}

/// One editable value: shown in the field picker, edited in the input box.
struct FieldRef {
    label: &'static str,
    file: PathBuf,
    key: &'static str,
    options: Vec<String>,
}

struct Field {
    label: &'static str,
    value: String,
    options: Vec<String>,
}

enum FormKind {
    Event,
    Speaker(usize),
}

enum Mode {
    Browse,
    Pick { fields: Vec<FieldRef>, sel: usize },
    Input { field: FieldRef, value: String },
    Form { kind: FormKind, fields: Vec<Field>, sel: usize },
}

struct App {
    root: PathBuf,
    events: Vec<Event>,
    items: Vec<Item>,
    list: ListState,
    mode: Mode,
    message: Option<(bool, String)>, // (is_error, text)
    quit: bool,
}

pub fn run(root: PathBuf) -> Result<()> {
    let mut app = App { root, events: vec![], items: vec![], list: ListState::default(), mode: Mode::Browse, message: None, quit: false };
    app.reload(None)?;
    let mut terminal = ratatui::init();
    let res = app.main_loop(&mut terminal);
    ratatui::restore();
    res
}

impl App {
    fn reload(&mut self, select_dir: Option<PathBuf>) -> Result<()> {
        let current = select_dir.or_else(|| self.selected_dir());
        self.events = model::scan(&self.root)?;
        self.items = self
            .events
            .iter()
            .enumerate()
            .flat_map(|(ei, e)| std::iter::once(Item::Event(ei)).chain((0..e.lectures.len()).map(move |li| Item::Lecture(ei, li))))
            .collect();
        let idx = current.and_then(|d| self.items.iter().position(|&i| self.item_dir(i) == d)).unwrap_or(0);
        self.list.select((!self.items.is_empty()).then_some(idx));
        Ok(())
    }

    fn item_dir(&self, item: Item) -> PathBuf {
        match item {
            Item::Event(e) => self.events[e].dir.clone(),
            Item::Lecture(e, l) => self.events[e].lectures[l].dir.clone(),
        }
    }

    fn selected(&self) -> Option<Item> {
        self.list.selected().and_then(|i| self.items.get(i).copied())
    }

    fn selected_dir(&self) -> Option<PathBuf> {
        self.selected().map(|i| self.item_dir(i))
    }

    fn main_loop(&mut self, terminal: &mut DefaultTerminal) -> Result<()> {
        while !self.quit {
            terminal.draw(|f| self.draw(f))?;
            if let TermEvent::Key(k) = event::read()? {
                if k.kind == KeyEventKind::Press {
                    self.on_key(k, terminal)?;
                }
            }
        }
        Ok(())
    }

    // ---- keys ----

    fn on_key(&mut self, k: KeyEvent, terminal: &mut DefaultTerminal) -> Result<()> {
        if k.modifiers.contains(KeyModifiers::CONTROL) && k.code == KeyCode::Char('c') {
            self.quit = true;
            return Ok(());
        }
        let mode = std::mem::replace(&mut self.mode, Mode::Browse);
        self.mode = match mode {
            Mode::Browse => return self.on_browse(k, terminal),
            Mode::Pick { fields, sel } => self.on_pick(k, fields, sel),
            Mode::Input { field, value } => self.on_input(k, field, value)?,
            Mode::Form { kind, fields, sel } => self.on_form(k, kind, fields, sel)?,
        };
        Ok(())
    }

    fn on_browse(&mut self, k: KeyEvent, terminal: &mut DefaultTerminal) -> Result<()> {
        self.message = None;
        let n = self.items.len();
        let sel = self.list.selected().unwrap_or(0);
        match k.code {
            KeyCode::Char('q') | KeyCode::Esc => self.quit = true,
            KeyCode::Down | KeyCode::Char('j') if n > 0 => self.list.select(Some((sel + 1).min(n - 1))),
            KeyCode::Up | KeyCode::Char('k') => self.list.select(Some(sel.saturating_sub(1))),
            KeyCode::Char('r') => {
                self.reload(None)?;
                self.info("načteno znovu");
            }
            KeyCode::Char('n') => self.mode = self.event_form(),
            KeyCode::Char('a') => match self.selected() {
                Some(Item::Event(e) | Item::Lecture(e, _)) => self.mode = self.speaker_form(e),
                None => self.error("nejdřív založ akci (n)"),
            },
            KeyCode::Char('e') | KeyCode::Enter => {
                let fields = self.field_refs();
                if !fields.is_empty() {
                    self.mode = Mode::Pick { fields, sel: 0 };
                }
            }
            KeyCode::Char('E') => match self.selected() {
                Some(Item::Event(e)) => self.open_editor(terminal, self.events[e].file())?,
                Some(Item::Lecture(e, l)) => self.open_editor(terminal, self.events[e].lectures[l].file())?,
                None => {}
            },
            KeyCode::Char('L') => match self.selected() {
                Some(Item::Lecture(e, l)) => self.open_editor(terminal, self.events[e].lectures[l].config_file())?,
                _ => self.error("lecture.json má jen přednáška"),
            },
            KeyCode::Char('o') => {
                if let Some(d) = self.selected_dir() {
                    let _ = Command::new("open").arg(d).status();
                }
            }
            _ => {}
        }
        Ok(())
    }

    fn on_pick(&mut self, k: KeyEvent, fields: Vec<FieldRef>, sel: usize) -> Mode {
        match k.code {
            KeyCode::Esc => Mode::Browse,
            KeyCode::Down | KeyCode::Char('j') => Mode::Pick { sel: (sel + 1).min(fields.len() - 1), fields },
            KeyCode::Up | KeyCode::Char('k') => Mode::Pick { sel: sel.saturating_sub(1), fields },
            KeyCode::Enter => {
                let field = fields.into_iter().nth(sel).expect("selection in range");
                let value = current_value(&field);
                Mode::Input { field, value }
            }
            _ => Mode::Pick { fields, sel },
        }
    }

    fn on_input(&mut self, k: KeyEvent, field: FieldRef, mut value: String) -> Result<Mode> {
        match k.code {
            KeyCode::Esc => return Ok(Mode::Browse),
            KeyCode::Enter => {
                match edit::set(&field.file, field.key, &value) {
                    Ok(()) => {
                        self.reload(None)?;
                        self.info(&format!("uloženo: {} = {value}", field.key));
                        return Ok(Mode::Browse);
                    }
                    Err(e) => self.error(&format!("{e:#}")),
                }
            }
            KeyCode::Left | KeyCode::Right if !field.options.is_empty() => {
                value = cycle(&field.options, &value, k.code == KeyCode::Right);
            }
            _ => edit_text(&mut value, k),
        }
        Ok(Mode::Input { field, value })
    }

    fn on_form(&mut self, k: KeyEvent, kind: FormKind, mut fields: Vec<Field>, mut sel: usize) -> Result<Mode> {
        let last = fields.len() - 1;
        match k.code {
            KeyCode::Esc => return Ok(Mode::Browse),
            KeyCode::Down | KeyCode::Tab => sel = (sel + 1).min(last),
            KeyCode::Up | KeyCode::BackTab => sel = sel.saturating_sub(1),
            KeyCode::Left | KeyCode::Right if !fields[sel].options.is_empty() => {
                fields[sel].value = cycle(&fields[sel].options, &fields[sel].value, k.code == KeyCode::Right);
            }
            KeyCode::Enter if sel < last => sel += 1,
            KeyCode::Enter => match self.submit(&kind, &fields) {
                Ok(dir) => {
                    self.reload(Some(dir.clone()))?;
                    self.info(&format!("založeno: {}", dir.strip_prefix(&self.root).unwrap_or(&dir).display()));
                    return Ok(Mode::Browse);
                }
                Err(e) => self.error(&format!("{e:#}")),
            },
            _ => edit_text(&mut fields[sel].value, k),
        }
        Ok(Mode::Form { kind, fields, sel })
    }

    fn submit(&self, kind: &FormKind, f: &[Field]) -> Result<PathBuf> {
        let v = |i: usize| f[i].value.trim().to_string();
        match kind {
            FormKind::Event => edit::new_event(
                &self.root,
                &NewEvent {
                    number: v(0).parse().map_err(|_| anyhow::anyhow!("číslo akce musí být celé číslo"))?,
                    date: v(1),
                    time: v(2),
                    venue: v(3),
                    image: v(4),
                    partner_logo: v(5),
                    partner_name: v(6),
                },
            ),
            FormKind::Speaker(e) => edit::add_speaker(
                &self.events[*e],
                &NewSpeaker {
                    name: v(0),
                    title: v(1),
                    photo: (!v(2).is_empty()).then(|| expand_home(&v(2))),
                    order: v(3).parse().ok(),
                    slug: Some(v(4)),
                    abstract_text: v(5),
                },
            ),
        }
    }

    fn event_form(&self) -> Mode {
        let next = self.events.iter().map(|e| e.number()).max().unwrap_or(0) + 1;
        let bgr = model::resource_options(&self.root, "bgr", &["png", "jpg"]);
        let logos = model::resource_options(&self.root, "logo", &["svg"]);
        let fields = vec![
            field("číslo", &next.to_string(), vec![]),
            field("datum (RRRR-MM-DD)", "", vec![]),
            field("čas", "18:00", vec![]),
            field("místo", "", vec![]),
            field("ilustrace ←→", bgr.first().map_or("", |s| s), bgr.clone()),
            field("logo partnera ←→", logos.first().map_or("", |s| s), logos.clone()),
            field("partner (prázdné = z loga)", "", vec![]),
        ];
        Mode::Form { kind: FormKind::Event, fields, sel: 1 }
    }

    fn speaker_form(&self, e: usize) -> Mode {
        let next = self.events[e].lectures.iter().map(|l| l.order()).filter(|&o| o != i64::MAX).max().unwrap_or(0) + 1;
        let fields = vec![
            field("jméno", "", vec![]),
            field("název přednášky", "", vec![]),
            field("fotka (cesta, zkopíruje se)", "", vec![]),
            field("pořadí", &next.to_string(), vec![]),
            field("složka (prázdné = příjmení)", "", vec![]),
            field("anotace", "", vec![]),
        ];
        Mode::Form { kind: FormKind::Speaker(e), fields, sel: 0 }
    }

    fn field_refs(&self) -> Vec<FieldRef> {
        let r = |label, file: &Path, key, options| FieldRef { label, file: file.to_path_buf(), key, options };
        match self.selected() {
            Some(Item::Event(e)) => {
                let f = self.events[e].file();
                vec![
                    r("název", &f, "name", vec![]),
                    r("datum", &f, "date", vec![]),
                    r("čas", &f, "time", vec![]),
                    r("místo", &f, "venue", vec![]),
                    r("web", &f, "url", vec![]),
                    r("ilustrace", &f, "image", model::resource_options(&self.root, "bgr", &["png", "jpg"])),
                    r("partner", &f, "partner.name", vec![]),
                    r("logo partnera", &f, "partner.logo", model::resource_options(&self.root, "logo", &["svg"])),
                ]
            }
            Some(Item::Lecture(e, l)) => {
                let lec = &self.events[e].lectures[l];
                let (t, c) = (lec.file(), lec.config_file());
                let photos = image_files(&lec.dir);
                let mut v = vec![
                    r("řečník", &t, "speaker", vec![]),
                    r("název", &t, "title", vec![]),
                    r("fotka", &t, "photo", photos),
                    r("pořadí", &t, "order", vec![]),
                    r("YouTube", &t, "youtube", vec![]),
                    r("anotace", &t, "body", vec![]),
                ];
                if lec.config.is_some() {
                    v.extend([
                        r("whisper prompt", &c, "whisper_prompt", vec![]),
                        r("ořez projekce w:h:x:y", &c, "projection_crop", vec![]),
                        r("tvar hlavy", &c, "head_shape", vec!["circle".into(), "square".into()]),
                        r("jazyk", &c, "language", vec![]),
                    ]);
                }
                v
            }
            None => vec![],
        }
    }

    fn open_editor(&mut self, terminal: &mut DefaultTerminal, file: PathBuf) -> Result<()> {
        let editor = std::env::var("VISUAL").or_else(|_| std::env::var("EDITOR")).unwrap_or_else(|_| "vi".into());
        ratatui::restore();
        let status = Command::new("sh").arg("-c").arg(format!("{editor} \"$1\"")).arg("sh").arg(&file).status();
        *terminal = ratatui::init();
        terminal.clear()?;
        self.reload(None)?;
        match status {
            Ok(s) if s.success() => self.info(&format!("upraveno: {}", model::file_name(&file))),
            _ => self.error(&format!("editor {editor} selhal")),
        }
        Ok(())
    }

    fn info(&mut self, m: &str) {
        self.message = Some((false, m.to_string()));
    }
    fn error(&mut self, m: &str) {
        self.message = Some((true, m.to_string()));
    }

    // ---- drawing ----

    fn draw(&mut self, f: &mut Frame) {
        let [main, footer] = Layout::vertical([Constraint::Min(1), Constraint::Length(1)]).areas(f.area());
        let [left, right] = Layout::horizontal([Constraint::Length(42), Constraint::Min(30)]).areas(main);

        let items: Vec<ListItem> = self
            .items
            .iter()
            .map(|&it| match it {
                Item::Event(e) => {
                    let ev = &self.events[e];
                    let bad = worst(&check::event(ev));
                    ListItem::new(Line::from(vec![
                        Span::styled(format!("{} ", ev.id()), Style::new().bold().fg(PURPLE)),
                        Span::raw(ev.get("date")),
                        mark(bad),
                    ]))
                }
                Item::Lecture(e, l) => {
                    let lec = &self.events[e].lectures[l];
                    let done = status::steps(lec).iter().filter(|s| matches!(s.state, State::Done | State::Skip)).count();
                    ListItem::new(Line::from(vec![
                        Span::raw(format!("  {:<11}", lec.id())),
                        Span::styled(format!("{done:>2}/14 "), Style::new().dark_gray()),
                        Span::raw(lec.get("speaker")),
                        mark(worst(&check::lecture(lec))),
                    ]))
                }
            })
            .collect();
        let list = List::new(items)
            .block(Block::bordered().title(" pehapkari ".bold()))
            .highlight_style(Style::new().bg(Color::Rgb(0x31, 0x2e, 0x81)).add_modifier(Modifier::BOLD));
        f.render_stateful_widget(list, left, &mut self.list);

        let detail = match self.selected() {
            Some(Item::Event(e)) => self.event_detail(&self.events[e]),
            Some(Item::Lecture(e, l)) => lecture_detail(&self.events[e].lectures[l]),
            None => vec![Line::raw("Žádná akce. Založ ji klávesou n.")],
        };
        let title = self.selected_dir().map(|d| format!(" {} ", d.strip_prefix(&self.root).unwrap_or(&d).display())).unwrap_or_default();
        f.render_widget(Paragraph::new(detail).wrap(Wrap { trim: false }).block(Block::bordered().title(title)), right);

        let help = match &self.mode {
            Mode::Browse => "↑↓ výběr  e upravit  E editor  L lecture.json  n nová akce  a řečník  o Finder  r obnovit  q konec",
            Mode::Pick { .. } => "↑↓ pole  Enter upravit  Esc zpět",
            Mode::Input { .. } => "Enter uložit  ←→ možnosti  Ctrl-U smazat  Esc zrušit",
            Mode::Form { .. } => "Tab/↑↓ pole  ←→ možnosti  Enter další / na posledním založit  Esc zrušit",
        };
        let footer_line = match &self.message {
            Some((true, m)) => Line::from(Span::styled(m.clone(), Style::new().fg(Color::Red).bold())),
            Some((false, m)) => Line::from(Span::styled(m.clone(), Style::new().fg(Color::Green))),
            None => Line::from(Span::styled(help, Style::new().dark_gray())),
        };
        f.render_widget(Paragraph::new(footer_line), footer);

        match &self.mode {
            Mode::Browse => {}
            Mode::Pick { fields, sel } => {
                let area = popup(f.area(), 60, fields.len() as u16 + 2);
                let lines: Vec<Line> = fields
                    .iter()
                    .enumerate()
                    .map(|(i, fr)| {
                        let v = current_value(fr);
                        let short: String = v.lines().next().unwrap_or("").chars().take(34).collect();
                        let style = if i == *sel { Style::new().reversed() } else { Style::new() };
                        Line::from(vec![Span::styled(format!("{:<22}", fr.label), style), Span::raw(format!(" {short}")).dark_gray()])
                    })
                    .collect();
                f.render_widget(Clear, area);
                f.render_widget(Paragraph::new(lines).block(Block::bordered().title(" upravit ")), area);
            }
            Mode::Input { field, value } => {
                let area = popup(f.area(), 70, 5);
                let mut lines = vec![Line::from(vec![Span::raw(value.clone()), Span::raw("▏").fg(PURPLE)])];
                if !field.options.is_empty() {
                    lines.push(Line::from(format!("←→ {} možností", field.options.len())).dark_gray());
                }
                f.render_widget(Clear, area);
                let title = format!(" {} ({} · {}) ", field.label, model::file_name(&field.file), field.key);
                f.render_widget(Paragraph::new(lines).wrap(Wrap { trim: false }).block(Block::bordered().title(title)), area);
            }
            Mode::Form { kind, fields, sel } => {
                let area = popup(f.area(), 76, fields.len() as u16 + 2);
                let title = match kind {
                    FormKind::Event => " nová akce ".to_string(),
                    FormKind::Speaker(e) => format!(" nový řečník – {} ", self.events[*e].id()),
                };
                let lines: Vec<Line> = fields
                    .iter()
                    .enumerate()
                    .map(|(i, fl)| {
                        let label = Span::styled(format!("{:<28}", fl.label), if i == *sel { Style::new().reversed() } else { Style::new() });
                        let cursor = if i == *sel { "▏" } else { "" };
                        Line::from(vec![label, Span::raw(format!(" {}", fl.value)), Span::raw(cursor).fg(PURPLE)])
                    })
                    .collect();
                f.render_widget(Clear, area);
                f.render_widget(Paragraph::new(lines).block(Block::bordered().title(title)), area);
            }
        }
    }

    fn event_detail(&self, e: &Event) -> Vec<Line<'static>> {
        let mut out = vec![
            Line::from(Span::styled(format!("{}. {}", e.number(), e.get("name")), Style::new().bold().fg(PURPLE))),
            Line::raw(""),
        ];
        for (label, key) in [("datum", "date"), ("čas", "time"), ("místo", "venue"), ("web", "url"), ("ilustrace", "image"), ("partner", "partner.name"), ("logo", "partner.logo")] {
            out.push(kv(label, &e.get(key)));
        }
        out.push(Line::raw(""));
        out.push(Line::from(format!("Přednášky ({}):", e.lectures.len())).bold());
        for l in &e.lectures {
            out.push(Line::raw(format!("  {}. {} – {}", l.get("order"), l.get("speaker"), l.get("title"))));
        }
        issues_block(&mut out, &check::event(e));
        out
    }
}

fn lecture_detail(l: &Lecture) -> Vec<Line<'static>> {
    let mut out = vec![
        Line::from(Span::styled(l.get("title"), Style::new().bold().fg(PURPLE))),
        Line::raw(""),
    ];
    for (label, key) in [("řečník", "speaker"), ("pořadí", "order"), ("fotka", "photo"), ("YouTube", "youtube")] {
        out.push(kv(label, &l.get(key)));
    }
    if let Some(cfg) = &l.config {
        for key in ["audio", "screen", "camera"] {
            let v = match &cfg[key] {
                serde_json::Value::String(s) => s.clone(),
                serde_json::Value::Array(a) => format!("{} částí", a.len()),
                _ => "–".into(),
            };
            out.push(kv(key, &v));
        }
    }
    out.push(Line::raw(""));
    out.push(Line::from("Pipeline:").bold());
    for s in status::steps(l) {
        let (sym, color) = match s.state {
            State::Done => ("✓", Color::Green),
            State::Stale => ("!", Color::Yellow),
            State::Missing => ("·", Color::DarkGray),
            State::Skip => ("-", Color::DarkGray),
        };
        out.push(Line::from(vec![
            Span::styled(format!("  {sym} {:>2} ", s.id), Style::new().fg(color)),
            Span::raw(format!("{:<11}", s.name)),
            Span::raw(s.note).dark_gray(),
        ]));
    }
    let abs = l.abstract_text();
    if !abs.is_empty() {
        out.push(Line::raw(""));
        out.push(Line::from("Anotace:").bold());
        out.push(Line::raw(abs));
    }
    issues_block(&mut out, &check::lecture(l));
    out
}

fn issues_block(out: &mut Vec<Line<'static>>, issues: &[Issue]) {
    if issues.is_empty() {
        return;
    }
    out.push(Line::raw(""));
    for i in issues {
        let (tag, color) = if i.level == Level::Error { ("chyba", Color::Red) } else { ("pozor", Color::Yellow) };
        out.push(Line::from(vec![Span::styled(format!("{tag} "), Style::new().fg(color).bold()), Span::raw(format!("{}: {}", i.file, i.msg))]));
    }
}

fn kv(label: &str, value: &str) -> Line<'static> {
    let v = if value.is_empty() { "–".to_string() } else { value.to_string() };
    Line::from(vec![Span::styled(format!("{label:<10}"), Style::new().dark_gray()), Span::raw(v)])
}

fn worst(issues: &[Issue]) -> Option<Level> {
    issues.iter().map(|i| i.level).fold(None, |a, l| Some(a.map_or(l, |a: Level| if l > a { l } else { a })))
}

fn mark(level: Option<Level>) -> Span<'static> {
    match level {
        Some(Level::Error) => Span::styled(" ✗", Style::new().fg(Color::Red)),
        Some(Level::Warn) => Span::styled(" !", Style::new().fg(Color::Yellow)),
        None => Span::raw(""),
    }
}

fn field(label: &'static str, value: &str, options: Vec<String>) -> Field {
    Field { label, value: value.to_string(), options }
}

fn current_value(f: &FieldRef) -> String {
    let Ok(text) = std::fs::read_to_string(&f.file) else { return String::new() };
    if model::file_name(&f.file) == "lecture.json" {
        let v: serde_json::Value = serde_json::from_str(&text).unwrap_or_default();
        return match &v[f.key] {
            serde_json::Value::String(s) => s.clone(),
            serde_json::Value::Null => String::new(),
            other => other.to_string(),
        };
    }
    let Some(fm) = crate::fm::FrontMatter::parse(&text) else { return String::new() };
    if f.key == "body" {
        fm.body.trim().replace('\n', " ")
    } else {
        fm.get(f.key).unwrap_or_default()
    }
}

fn cycle(options: &[String], current: &str, forward: bool) -> String {
    let n = options.len();
    let i = options.iter().position(|o| o == current);
    let next = match (i, forward) {
        (None, _) => 0,
        (Some(i), true) => (i + 1) % n,
        (Some(i), false) => (i + n - 1) % n,
    };
    options[next].clone()
}

fn edit_text(value: &mut String, k: KeyEvent) {
    match k.code {
        KeyCode::Char('u') if k.modifiers.contains(KeyModifiers::CONTROL) => value.clear(),
        KeyCode::Char(c) => value.push(c),
        KeyCode::Backspace => {
            value.pop();
        }
        _ => {}
    }
}

fn image_files(dir: &Path) -> Vec<String> {
    let mut v: Vec<String> = std::fs::read_dir(dir)
        .into_iter()
        .flatten()
        .flatten()
        .map(|e| model::file_name(&e.path()))
        .filter(|n| {
            let l = n.to_lowercase();
            (l.ends_with(".jpg") || l.ends_with(".jpeg") || l.ends_with(".png")) && !l.starts_with("event-") && !l.starts_with("video-")
        })
        .collect();
    v.sort();
    v
}

fn expand_home(p: &str) -> PathBuf {
    match (p.strip_prefix("~/"), std::env::var("HOME")) {
        (Some(rest), Ok(home)) => Path::new(&home).join(rest),
        _ => PathBuf::from(p),
    }
}

fn popup(area: Rect, width: u16, height: u16) -> Rect {
    let w = width.min(area.width.saturating_sub(4));
    let h = height.min(area.height.saturating_sub(2));
    Rect { x: area.x + (area.width - w) / 2, y: area.y + (area.height - h) / 3, width: w, height: h }
}
