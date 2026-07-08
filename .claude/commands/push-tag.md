# Push & Tag

Commit all changes, create the next version tag, and push everything to GitHub in one shot.

## Steps

1. Run `git status` and `git diff --stat` to see what changed
2. Run `git log --oneline -3` to see recent commits and the commit message style
3. Run `git tag --sort=-v:refname | head -5` to find the latest tag and determine the next version number (increment the patch number, e.g. v4.3 → v4.4)
4. Stage all changed files with `git add` (specific files, not `-A`)
5. Commit with a concise message summarizing what changed, ending with:
   Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
6. Create an annotated tag with the next version number
7. Push the commit and the tag: `git push && git push --tags`
8. Report back: what was committed, what tag was created
