You are compressing ONE PART of a long coding-agent session so that a
later pass can write a wiki page from all the parts together.

## Input

`{meta}` carries the session metadata plus a `chunk` object:
`index` (0-based), `total`, and `turns` (the turn range in this part).

The transcript part is below. It may contain user messages, assistant
reasoning, tool calls and their output.

## Output

Return only a dense bullet list — no frontmatter, no headings, no
suggested-tags comment. At most 20 bullets, each under 200 characters.

Extract, in this order of importance:

- what the user was trying to achieve in this part;
- decisions made and the reason given;
- concrete facts: file paths, function/class names, commands, config
  values, versions, URLs, numbers;
- errors and how they were resolved (or left unresolved);
- the outcome: what changed, what was verified, what is still open;
- one or two short verbatim quotes when the wording matters.

If the part is mostly tool output, say what the tool produced and which
task it served instead of repeating the output. Do not invent anything
that is not in the part. Do not copy long code blocks — name the file
and the change.

{language}

## Session part

```markdown
{body}
```