ROUND 1
Seen in one second: A possession review tool with a single action to load a submission CSV.
Idea (one sentence): One frame-label row becomes one point in a full-match possession strip.
Live thing: Load a local CSV, select any frame on the strip, and inspect its adjacent label runs.
Layout words by section: shell=contract rail / heading=action row / import=drop area / summary=divided strip / timeline=full-width data band / inspection=selected frame and run list.
Scores: design 7 · usability 8 · creativity 7 · content 8 -> overall 7.5
Caps applied: None. The empty-state screen has no candidate data, so it intentionally shows no invented timeline values.
Top three problems (most visible first), each with the screenshot it shows in and the fix:
1. desktop-fold.jpg: the timeline has no colored marks until a valid candidate file is loaded. This is intentional to avoid sample predictions; once loaded, the strip is drawn from the actual CSV labels.
2. desktop-fold.jpg and mobile-fold.jpg: most secondary labels are 11-12px. The app-screen guidance allows this for metadata and axis labels, though the inspector still reports that much of the text is under 13px.
3. No loaded-data screenshot was produced because no candidate submission was available in the project folder. Parser tests cover a generated full-length fixture; confirm the visual run list with the provided candidate CSV.

App-screen checks:
- The title and primary job are visible first; upload is the main action.
- The timeline is the largest data block and uses the challenge's four label categories.
- The pitch-green frame and the teal home series give the interface its face.
- All displayed counts and run boundaries come from the selected CSV; no score or match result is fabricated.
- Missing values use a neutral dash. A valid file produces real label colors and exact frame navigation.
- The legend names each timeline color, and the phone layout folds the side context above the review screen.
