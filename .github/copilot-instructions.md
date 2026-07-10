# GitHub Copilot Instructions

## Flutter App Build Policy

The Flutter app under app/bluetooth_flutter_Trace must not be built locally.

- Do not run local build or packaging commands such as `flutter build`, `gradle build`, `./gradlew assemble*`, `xcodebuild`, `dart compile`, or platform package/signing commands.
- Use GitHub Actions for all compile/build verification and release artifacts.
- Local non-build checks are allowed when useful, such as formatting, static analysis, tests that do not invoke a build, and file/content inspection.
- If a task requires a real build result, trigger or inspect the relevant GitHub Actions workflow instead of attempting a local build.

This restriction does not apply to the MCU firmware or LVGL simulator. Follow
the repository AGENTS.md build instructions for those targets.
