You are merging several digests of consecutive parts of one long
coding-agent session. The merged digest will be merged again or used
to write the final wiki page.

## Input

`{meta}` carries the session metadata plus a `merge` object with the
batch `index` and `total`.

## Output

Return only a dense bullet list — no frontmatter, no headings, no
suggested-tags comment. Keep it shorter than the input: at most 20
bullets, each under 200 characters.

Keep the through-line of the session:

- the goal and the decisions that shaped it;
- facts, paths, commands and outcomes worth carrying forward;
- contradictions or changes of direction (say both sides);
- what remains open.

Drop repetition, tool noise, and anything that only made sense inside
one part. Do not invent anything. {language}

## Digests to merge

```markdown
{body}
```