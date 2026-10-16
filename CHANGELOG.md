# Changelog

User-facing changes are listed here. See the source and commit history for
implementation details.

## [Unreleased]

### Added

- Separate challenger evidence folders, so original analysis results and rerun
  results can be reviewed independently.
- Checks for changes to original evidence. A challenge cannot be confirmed if
  those checks find changes or cannot verify the originals.
- Warnings when optional analysis guides are unavailable.

### Changed

- Challengers are instructed to question both the evidence and the conclusion.
  Repeating the same result is no longer enough to confirm a report.
- Required guidance is supplied automatically in workflow order. Optional guides
  are loaded when relevant.
- Agents share GitHub alert reads within a run to reduce duplicate requests.
  Facts can be refreshed; live credential tests are not cached.
- Updated the Copilot integration and default agent models. Each stage uses its
  configured model and tools; the default judge reviews reports without tools.

### Fixed

- Alert tools now return full details and location pages instead of summaries.
  Fixed a response-format error that prevented some alerts from being read.
- Challenger reruns no longer execute in the original analysis workspace.
- Fixed cases where challenger instructions were not applied and evidence paths
  were not resolved correctly.
- Improved support for installed packages and relative output directories.
- Log messages no longer disrupt the live progress display.
- Corrected guidance coverage, confidence labels, and duration reporting for
  newer SDK versions. Early session events are now captured.
