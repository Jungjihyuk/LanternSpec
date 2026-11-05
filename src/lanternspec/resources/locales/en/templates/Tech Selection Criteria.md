---
id: CUR-tech-criteria
type: current
status: ${current_status.active}
created: ${today}
updated: ${today}
links: []
template: Tech Selection Criteria
template_version: 1.0.0
based_on: 1.0.0
---
# 📘 Tech Selection Criteria

> [!abstract] At a glance
> The criteria and order for choosing a project's technologies.
> `/l-init` uses everything up to the decision tree.
> Decisions that come after the technologies are set, such as design patterns, refer to these criteria when writing an ADR.
> Reference date: 2026-11-06

## Roles of the criteria
- **Required:** A candidate that fails it is dropped.
- **Required on demand:** Filters candidates only when the project has that need.
- **Comparison:** Weighs the remaining candidates.

| Table | Required | Required on demand | Comparison |
|---|---|---|---|
| Common | Functional fit, Security, Compatibility | Performance, Scalability (with target numbers) | Productivity, Cost, Maintainability, Reliability, Ecosystem maturity, Deployment · Operations, Technology sustainability |
| Web | Browser compatibility | Rendering, SEO, Accessibility | Initial load |
| Desktop | OS support | System APIs, Hardware access, Offline, Local security | Runtime performance, Startup time, Install size, Native UX |
| Mobile | Platform coverage, Store policy, OS updates | Native APIs, Background execution, Offline support, Accessibility | Battery use, Memory limits, UI responsiveness, App size |
| Server | None | Authentication · Authorization, Real-time, API style, Background jobs | Server scalability |
| DB | Backup · Recovery | Data consistency, Data model | Query patterns, Data scaling, Schema changes |
| Infrastructure | None | Data location | Infrastructure cost, Deployment strategy, Operating model, Autoscaling, Monitoring · Logs, Disaster recovery |

Existing services (Supabase, Firebase and so on) are judged by the common criteria plus data model, data consistency, infrastructure cost and data location.

## Evaluation criteria

### Common
| Area | What to check |
|---|---|
| Functional fit | Can it actually implement the required features? |
| Performance | Does it meet the target response time and throughput? |
| Scalability | Can it cope as users and data grow? |
| Productivity | Can it be built within the planned time? |
| Cost | What is the total cost from development through operation? |
| Maintainability | How easy are changes, fixes and tests? |
| Security | Does it meet the required security level and regulations? |
| Reliability | How well does the service withstand failures and errors? |
| Compatibility | Does it run on the target OSes, devices and browsers? |
| Ecosystem maturity | Are libraries, tools, documentation and support sufficient? |
| Deployment · Operations | How complex are deployment, updates and monitoring? |
| Technology sustainability | What are the long-term support, lock-in and replacement risks? |

### Web
| Area | What to check |
|---|---|
| Rendering | Does it offer the CSR, SSR or SSG approach the requirements need? |
| Initial load | Does it meet perceived performance such as initial JavaScript size, LCP and INP? |
| SEO | Does it meet search engine exposure and crawling needs? |
| Browser compatibility | Does it run on Chrome, Safari, mobile browsers and so on? |
| Accessibility | Does it meet keyboard operation, screen readers and WCAG? |

### Desktop
| Area | What to check |
|---|---|
| OS support | Does it support the needed OSes among Windows, macOS and Linux? |
| System APIs | Can it use the file system, processes, notifications and accessibility APIs? |
| Hardware access | Can it reach the GPU, camera and USB? |
| Runtime performance | Are CPU · GPU throughput and memory use acceptable? |
| Startup time | Are launch and initialization times acceptable? |
| Install size | Are the package size and bundled runtime acceptable? |
| Offline | How much works without a network? |
| Native UX | Does it follow each OS's menus, shortcuts and window behavior? |
| Local security | Does it support local data protection, permissions and code signing? |

### Mobile
| Area | What to check |
|---|---|
| Platform coverage | Does it support the needed range among iOS, Android and tablets? |
| Battery use | Are background work, sensors and network use acceptable? |
| Memory limits | Can it cope with low-end devices and app process termination? |
| UI responsiveness | Are frame times, scrolling and animation smooth? |
| Native APIs | Can it use the camera, GPS, Bluetooth and NFC? |
| Background execution | Does it work within each OS's limits on scheduled work? |
| Offline support | Does it support local storage, sync and conflict resolution? |
| App size | Are the install file and download size acceptable? |
| Store policy | Does it meet review, payment policy and privacy requirements? |
| OS updates | Is it compatible with new OS versions? |
| Accessibility | Does it support system fonts, screen readers and input methods? |

### Server
| Area | What to check |
|---|---|
| Server scalability | Can it cope with traffic, concurrent connections and data throughput? |
| Real-time | Does it support what's needed, such as WebSocket or SSE? |
| API style | Can it easily build what's needed among REST, GraphQL and gRPC? |
| Authentication · Authorization | Can it safely implement login, permissions and social login? |
| Background jobs | Does it support scheduled jobs, queues and long-running work? |

### DB
| Area | What to check |
|---|---|
| Data consistency | Does it meet transaction, concurrency and integrity needs? |
| Data model | Does relational, document, key-value or vector fit the data? |
| Query patterns | Can it handle frequent queries, aggregation and search quickly? |
| Data scaling | Can replication or partitioning cope as data grows? |
| Schema changes | Can the schema change safely while the service runs? |
| Backup · Recovery | Can it recover to a chosen point in time? |

### Infrastructure
`/l-init` doesn't ask about this. Decide from this table before deploying.

| Area | What to check |
|---|---|
| Infrastructure cost | What does it cost by requests, server use and data transfer? |
| Deployment strategy | Does it support CDN, caching, zero-downtime deployment and rollback? |
| Operating model | Which of serverless, containers or virtual servers can the team run? |
| Autoscaling | Can resources follow changes in use? |
| Monitoring · Logs | Can failures be noticed quickly and their causes found? |
| Disaster recovery | How quickly can it recover from a failure? |
| Data location | Can data stay in the needed region to meet regulations? |

## Decision tree
First ask "Is there a language or framework you want to use?" If there is, use it and follow the tree only for what's still undecided. Each path has at most three new questions, counting this one.

### Screens: web
"Does it need to show up well in search results?" (Basis: SEO, Rendering)
- Yes — sites people find through search for the first time, like online stores, blogs and service introduction pages → Next.js
- No — screens only signed-up people use, like admin screens and internal tools → React + Vite

### Screens: desktop
"What matters most for this program?" (Basis: OS support, Productivity, Runtime performance, Hardware access, Native UX)
- Building quickly for several OSes (recommended) → Electron. Show Tauri as the alternative when install size and memory must be small.
- High performance or hardware control on several OSes → Qt
- Optimized for Windows → .NET + WinUI 3
- Optimized for macOS → SwiftUI

### Screens: mobile
"What matters most for this app?" (Basis: Platform coverage, Productivity, UI responsiveness, Native APIs)
- Building iOS and Android quickly from one codebase (recommended) → React Native + Expo
- Making iOS and Android screens identical → Flutter
- iOS only → SwiftUI
- Android only → Kotlin + Jetpack Compose

### Building several screens
- Web and desktop: don't ask the desktop question. Propose Electron and show Tauri as the alternative. They can share the web screen code.
- Mobile and another screen: don't ask the mobile question. Propose React Native + Expo. Screens can stay on TypeScript.

### Server and DB
Follow the answer to the server question.

- Not needed: no server to choose. If a desktop or mobile app stores data, propose SQLite.
- Use an existing service: recommend Supabase and show Firebase as the alternative. Suggest Firebase when offline use matters on mobile.
- Build it yourself: ask "What matters most for the server?" (Basis: Productivity, Reliability, Server scalability, Maintainability)
  - Building quickly, or AI · data processing (recommended) → FastAPI
  - Using the same language as the screens → NestJS (show only when the screens use TypeScript)
  - Reliability comes first, as in finance or the public sector → Spring Boot
  - Handling many concurrent connections → Go

When building the server yourself, don't ask about the DB. Propose PostgreSQL and show MySQL and SQLite as alternatives. (Basis: Data consistency, Data model)

## Technology comparison
Status is one of Recommended, Conditional or Not recommended. Change the status of a technology no longer suggested instead of deleting its row.

| Technology | Role | Language · Runtime | Status | Pros | Cons | To review |
|---|---|---|---|---|---|---|
| Next.js | Web screens | TypeScript · Node.js | Recommended | CSR, SSR and SSG in one framework | Complex rendering and caching | SSR needs a Node.js runtime |
| React + Vite | Web screens | TypeScript · Node.js | Recommended | Simple structure, deploys as static files | CSR by default, weak for SEO | Choose routing and data tools separately |
| Electron | Desktop screens | TypeScript · Chromium + Node.js | Recommended | Web technology for Windows, macOS and Linux with few screen differences | Large install size and memory use from bundling Chromium | Frequent upgrades from short major support, code signing |
| Tauri | Desktop screens | TypeScript + Rust · OS WebView | Conditional | Small install size by using the OS WebView | Must test WebView differences per OS; native features may need Rust | WebView environment on Linux, code signing |
| Qt | Desktop screens | C++ · QML | Conditional | Native performance, hardware access, several OSes | Steep learning and complex builds and deployment | LGPL · GPL · commercial license terms and cost |
| .NET + WinUI 3 | Desktop screens | C# · .NET | Conditional | Optimized for Windows features and UX, Visual Studio tools | Windows only | Consider WPF for existing WPF assets |
| SwiftUI | Desktop screens, mobile screens | Swift | Conditional | Optimized for macOS and iOS UX and the latest features | Apple platforms only | Needs a Mac and Xcode, Apple Developer Program at 99 USD a year, check signing and notarization for distribution outside the App Store, no code reuse for a later Android app |
| React Native + Expo | Mobile screens | TypeScript · React Native | Recommended | One codebase for iOS and Android, approachable for web developers, React Native recommends a framework for new projects | Special native features may need Swift or Kotlin code | Frequent version upgrades, minimum supported OS versions |
| Flutter | Mobile screens | Dart | Conditional | Easy to keep screens identical across platforms | Requires learning Dart; can differ from the OS's default UI | App size, native plugin support |
| Kotlin + Jetpack Compose | Mobile screens | Kotlin | Conditional | Optimized for Android UX and the latest features | Android only | No code reuse for a later iOS app |
| FastAPI | Server | Python | Recommended | Fast to build, generates OpenAPI documents, connects easily to AI · data libraries | Authentication, admin screens and project structure are up to you | Understanding async code, pre-1.0 version |
| NestJS | Server | TypeScript · Node.js | Conditional | Same language as the screens, provides modules and dependency injection | Decorators and framework concepts take learning | No published end-of-support schedule |
| Spring Boot | Server | Java · JVM | Conditional | Mature transactions, security and operations features | Much to learn and set up | Java or Kotlin experience, free support period of 4.x |
| Go | Server | Go | Conditional | Easy concurrency, deploys as a single binary | Few web framework features, more to build yourself | Choosing a framework (standard `net/http` and so on) |
| PostgreSQL | DB | SQL | Recommended | Strong transactions and integrity, rich JSON and extensions | Large-scale write scaling needs design | Running it yourself or using a managed service |
| MySQL | DB | SQL | Conditional | Many operating examples and hosting choices | Fewer advanced SQL and extension features than PostgreSQL | When it's a company standard or the team has run it before |
| SQLite | DB, local storage | SQL | Conditional | Runs inside the app from one file with no separate server | Weak for concurrent writes and multiple servers; device sync is up to you | Single-user tools, small services, local storage on desktop · mobile, encrypting stored data |
| Supabase | Existing service | PostgreSQL | Recommended | DB, authentication, storage and real-time together, uses SQL, self-hostable | Code can become tied to platform features | Pricing, data location, access rule design |
| Firebase | Existing service | Firestore (document NoSQL) | Conditional | Real-time sync and offline support, easy mobile integration | Weak for complex relations and aggregation, tied to Google services | Cost by reads and writes |

## Technology details
Bump the last digit of the template version when only these details are refreshed, and the middle digit when recommendations change: a technology added, a status changed or the tree changed.

| Technology | Checked version | End of support | License | Checked on | Official source |
|---|---|---|---|---|---|
| Next.js | 16.4.5 | Not set (Active LTS until the next major) | MIT | 2026-11-06 | [Support policy](https://nextjs.org/support-policy) |
| React + Vite | React 19.3.1, Vite 8.3.6 | No published schedule | MIT | 2026-11-06 | [React](https://react.dev), [Vite](https://vite.dev) |
| Electron | 45.2.3 | Only the latest 3 stable majors. 45 until 2027-04-27 (tentative) | MIT | 2026-11-06 | [Support policy](https://www.electronjs.org/docs/latest/tutorial/electron-timelines), [Schedule](https://releases.electronjs.org/schedule) |
| Tauri | 2.12.5 | No published schedule | Apache-2.0 or MIT | 2026-11-06 | [Documentation](https://v2.tauri.app/start/) |
| Qt | 6.12.0 | Commercial standard support 2031-09-30 | LGPL · GPL or commercial | 2026-11-06 | [Releases](https://doc.qt.io/qt-6/qt-releases.html), [Licensing](https://www.qt.io/licensing/) |
| .NET + WinUI 3 | .NET 10.0.14 (LTS), Windows App SDK 2.6.5 | .NET 10 until 2028-11-14, Windows App SDK 2.0 until 2027-04-29 | MIT | 2026-11-06 | [.NET support policy](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core), [Windows App SDK](https://learn.microsoft.com/en-us/windows/apps/windows-app-sdk/release-channels) |
| SwiftUI | Xcode 27.2 | No published schedule | Check the Apple SDK terms | 2026-11-06 | [Xcode support table](https://developer.apple.com/support/xcode/) |
| React Native + Expo | React Native 0.88.1, Expo SDK 58 | No fixed dates. React Native supports the latest 3 minor series, and Expo ships an SDK three times a year | MIT | 2026-11-06 | [React Native releases](https://reactnative.dev/docs/releases), [Expo](https://docs.expo.dev/versions/latest/) |
| Flutter | 3.47.9, Dart 3.13.7 | No published schedule | BSD-3-Clause | 2026-11-06 | [Releases](https://docs.flutter.dev/release/archive) |
| Kotlin + Jetpack Compose | Kotlin 2.4.21, Compose BOM 2026.09.00 | Kotlin 2.4 until 2027-12-03 | Apache-2.0 | 2026-11-06 | [Kotlin releases](https://kotlinlang.org/docs/releases.html), [Compose](https://developer.android.com/develop/ui/compose/documentation) |
| FastAPI | 0.162.0 | No published schedule | MIT | 2026-11-06 | [Documentation](https://fastapi.tiangolo.com) |
| NestJS | 12.3.3 | No published schedule | MIT | 2026-11-06 | [Documentation](https://docs.nestjs.com) |
| Spring Boot | 4.1.2 | Open source 2027-07-31, commercial 2028-07-31 | Apache-2.0 | 2026-11-06 | [Support schedule](https://api.spring.io/projects/spring-boot/generations) |
| Go | 1.27.3 | Until two newer majors are released | BSD-3-Clause | 2026-11-06 | [Release policy](https://go.dev/doc/devel/release) |
| PostgreSQL | 18.6 | 2030-11-14 | PostgreSQL License | 2026-11-06 | [Versioning policy](https://www.postgresql.org/support/versioning/) |
| MySQL | 9.7.4 (LTS) | LTS has 5 years of premier and 3 years of extended support | GPL-2.0 or commercial | 2026-11-06 | [Release model](https://dev.mysql.com/doc/refman/9.7/en/mysql-releases.html), [Licensing](https://www.mysql.com/about/legal/licensing/oem/) |
| SQLite | 3.54.1 | No published schedule | Public Domain | 2026-11-06 | [Copyright](https://www.sqlite.org/copyright.html) |
| Supabase | JS client 2.119.0 | Not applicable to a hosted service | Apache-2.0 (self-hosted) | 2026-11-06 | [Repository](https://github.com/supabase/supabase) |
| Firebase | JS SDK 13.2.0 | Not applicable to a hosted service | SDK under Apache-2.0, service under Google's terms | 2026-11-06 | [Firestore documentation](https://firebase.google.com/docs/firestore) |

## Store requirements
Mobile apps check these before release, whatever the technology.

| Store | Requirement | Checked on | Official source |
|---|---|---|---|
| Google Play | From 2026-08-31, new apps and updates must target Android 16 (API 36) or higher | 2026-11-06 | [Target API level](https://developer.android.com/google/play/requirements/target-sdk) |
| App Store | Use in-app purchase to unlock digital content or features in the app (3.1.1) | 2026-11-06 | [Review guidelines](https://developer.apple.com/app-store/review/guidelines/) |
| App Store | Link a privacy policy in the app and the store metadata (5.1.1(i)) | 2026-11-06 | [Review guidelines](https://developer.apple.com/app-store/review/guidelines/) |
| App Store | Offer account deletion in the app when it supports account creation (5.1.1(v)) | 2026-11-06 | [Review guidelines](https://developer.apple.com/app-store/review/guidelines/) |

## What to record in an ADR
- The chosen technology and the alternatives considered
- The evaluation criteria it was based on
- This document's reference date and template version

<!-- lantern:template-only -->
## Change log
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-11-06 | Base template |
