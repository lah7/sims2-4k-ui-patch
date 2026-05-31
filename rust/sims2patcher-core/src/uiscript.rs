use crate::error::{PatchError, Result};

const ALWAYS_QUOTED: &[&str] = &["caption", "tiptext", "wparam", "initvalue"];

#[derive(Clone, Debug, Default)]
pub struct UiScriptRoot {
    pub comments: Vec<String>,
    pub children: Vec<UiScriptElement>,
}

impl UiScriptRoot {
    pub fn visit_elements_mut<F>(&mut self, visitor: &mut F)
    where
        F: FnMut(&mut UiScriptElement),
    {
        fn visit<F>(element: &mut UiScriptElement, visitor: &mut F)
        where
            F: FnMut(&mut UiScriptElement),
        {
            visitor(element);
            for child in &mut element.children {
                visit(child, visitor);
            }
        }

        for child in &mut self.children {
            visit(child, visitor);
        }
    }
}

#[derive(Clone, Debug, Default)]
pub struct UiScriptElement {
    pub attributes: Vec<Attribute>,
    pub children: Vec<UiScriptElement>,
}

#[derive(Clone, Debug)]
pub struct Attribute {
    pub key: String,
    pub value: String,
}

impl UiScriptElement {
    pub fn get(&self, key: &str) -> Option<&str> {
        self.attributes
            .iter()
            .find(|attribute| attribute.key == key)
            .map(|attribute| attribute.value.as_str())
    }

    pub fn set(&mut self, key: &str, value: impl Into<String>) {
        if let Some(attribute) = self
            .attributes
            .iter_mut()
            .find(|attribute| attribute.key == key)
        {
            attribute.value = value.into();
        } else {
            self.attributes.push(Attribute {
                key: key.to_string(),
                value: value.into(),
            });
        }
    }
}

pub fn serialize(data: &str) -> Result<UiScriptRoot> {
    let mut root = UiScriptRoot::default();
    let mut lines: Vec<String> = data
        .split('\n')
        .map(|line| line.trim().to_string())
        .collect();
    lines.reverse();

    let mut hierarchy: Vec<Vec<UiScriptElement>> = vec![Vec::new()];
    let mut last_element: Option<UiScriptElement> = None;

    while let Some(mut line) = lines.pop() {
        if line.is_empty() {
            continue;
        }

        if line.starts_with('<') && !line.ends_with('>') {
            let mut merged = vec![line];
            loop {
                let Some(next) = lines.pop() else {
                    return Err(PatchError::InvalidDbpf(
                        "expected closing UI script tag".to_string(),
                    ));
                };
                let trimmed = next.trim().to_string();
                let done = trimmed.ends_with('>');
                merged.push(trimmed);
                if done {
                    break;
                }
            }
            line = merged.join("\\r\\n");
        }

        if line.starts_with('#') || !line.starts_with('<') {
            root.comments.push(line);
            continue;
        }

        if line == "<CHILDREN>" {
            let Some(element) = last_element.take() else {
                return Err(PatchError::InvalidDbpf(
                    "CHILDREN without parent element".to_string(),
                ));
            };
            hierarchy.last_mut().expect("root hierarchy").push(element);
            hierarchy.push(Vec::new());
            continue;
        }

        if line == "</CHILDREN>" {
            if let Some(element) = last_element.take() {
                hierarchy.last_mut().expect("root hierarchy").push(element);
            }
            let Some(children) = hierarchy.pop() else {
                return Err(PatchError::InvalidDbpf(
                    "unexpected CHILDREN close".to_string(),
                ));
            };
            let Some(parent) = hierarchy.last_mut().and_then(|items| items.last_mut()) else {
                return Err(PatchError::InvalidDbpf(
                    "CHILDREN close without parent".to_string(),
                ));
            };
            parent.children = children;
            continue;
        }

        if line.starts_with("<LEGACY") {
            if let Some(element) = last_element.take() {
                hierarchy.last_mut().expect("root hierarchy").push(element);
            }
            last_element = Some(read_element(&line));
        }
    }

    if let Some(element) = last_element.take() {
        hierarchy.last_mut().expect("root hierarchy").push(element);
    }

    if hierarchy.len() != 1 {
        return Err(PatchError::InvalidDbpf(
            "missing </CHILDREN> in UI script".to_string(),
        ));
    }

    root.children = hierarchy.pop().unwrap_or_default();
    Ok(root)
}

pub fn deserialize(root: &UiScriptRoot) -> String {
    fn process_element(element: &UiScriptElement, indent: usize, lines: &mut Vec<String>) {
        let indentation = "   ".repeat(indent);
        let attrs = element
            .attributes
            .iter()
            .map(|attribute| {
                let mut value = attribute.value.clone();
                if value.contains(' ') || ALWAYS_QUOTED.contains(&attribute.key.as_str()) {
                    value = value.replace("\\r", "\r").replace("\\n", "\n");
                    format!("{}=\"{}\"", attribute.key, value)
                } else {
                    format!("{}={}", attribute.key, value)
                }
            })
            .collect::<Vec<_>>()
            .join(" ");

        lines.push(format!("{indentation}<LEGACY {attrs} >"));
        if !element.children.is_empty() {
            lines.push(format!("{indentation}<CHILDREN>"));
            for child in &element.children {
                process_element(child, indent + 1, lines);
            }
            lines.push(format!("{indentation}</CHILDREN>"));
        }
    }

    let mut lines = Vec::new();
    lines.extend(root.comments.iter().cloned());
    for child in &root.children {
        process_element(child, 0, &mut lines);
    }
    format!("{}\r\n", lines.join("\r\n"))
}

fn read_element(line: &str) -> UiScriptElement {
    let mut body = line.trim();
    body = body.strip_prefix("<LEGACY").unwrap_or(body).trim();
    body = body.strip_suffix('>').unwrap_or(body).trim();
    if let Some(stripped) = body.strip_suffix('/') {
        body = stripped.trim();
    }

    let mut attributes = Vec::new();
    for token in tokenize_attributes(body) {
        if let Some(eq_pos) = token.find('=') {
            let key = token[..eq_pos].to_string();
            let mut value = token[eq_pos + 1..].to_string();
            if value.starts_with('"') && value.ends_with('"') && value.len() >= 2 {
                value = value[1..value.len() - 1].to_string();
            }
            attributes.push(Attribute { key, value });
        } else if !token.is_empty() {
            attributes.push(Attribute {
                key: token,
                value: String::new(),
            });
        }
    }

    UiScriptElement {
        attributes,
        children: Vec::new(),
    }
}

fn tokenize_attributes(data: &str) -> Vec<String> {
    let mut tokens = Vec::new();
    let mut current = String::new();
    let mut in_quote = false;

    for ch in data.chars() {
        if ch == '"' {
            in_quote = !in_quote;
            current.push(ch);
        } else if ch.is_whitespace() && !in_quote {
            if !current.is_empty() {
                tokens.push(std::mem::take(&mut current));
            }
        } else {
            current.push(ch);
        }
    }

    if !current.is_empty() {
        tokens.push(current);
    }
    tokens
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn serialize_and_deserialize_simple_script() {
        let data = "# Test\r\n<LEGACY iid=IGZWinGen area=(5,10,15,20) >\r\n<LEGACY iid=IGZWinText caption=\"Needs\" >\r\n";
        let root = serialize(data).unwrap();
        assert_eq!(deserialize(&root), data);
    }

    #[test]
    fn preserves_duplicate_attributes() {
        let data = "<LEGACY wparam=\"one\" wparam=\"two words\" >\r\n";
        let root = serialize(data).unwrap();
        assert_eq!(deserialize(&root), data);
    }
}
