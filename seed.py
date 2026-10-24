"""
seed.py — Pre-populates DevPulse DB with 8 realistic, high-signal tech stories.
Includes both deep technical metadata and beginner-friendly Plain English summaries & Jargon Busters.

Run standalone:  python seed.py
Or called from main.py startup if DB is empty.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete

from database import AsyncSessionLocal, init_db
from models import Article

logger = logging.getLogger(__name__)

def _dt(hours_ago: int) -> datetime:
    return datetime.now(tz=timezone.utc) - timedelta(hours=hours_ago)


SEED_ARTICLES: list[dict] = [
    # ── 1. Critical PHP Bug ─────────────────────────────────────────────────
    {
        "source_url": "https://www.php.net/security/advisories/2024-11-15-1",
        "source_domain": "php.net",
        "original_title": "PHP Core: Critical Use-After-Free in FPM Worker Recycling (CVE-2024-8929)",
        "published_at": _dt(6),
        "hn_score": 487,
        "hn_comments": 312,
        "hn_item_id": 42081337,
        "clean_title": "PHP FPM Use-After-Free Bug (CVE-2024-8929) Allows Remote Code Execution via Crafted Multipart Requests",
        "simple_title": "Serious PHP Flaw Lets Hackers Take Over Web Servers via File Uploads",
        "simple_badge": "🚨 Urgent Security Fix Needed",
        "category": "bugs_cves",
        "tags": json.dumps(["#PHP", "#RCE", "#CVE", "#FPM"]),
        "importance_badge": "🚨 Critical RCE — PHP FPM",
        "technical_depth_score": 9,
        "importance_score": 98.0,
        "is_daily_briefing": True,
        "plain_english_summary": (
            "PHP powers over 75% of websites (including WordPress and Wikipedia). "
            "A flaw in how PHP processes file uploads lets hackers send a corrupt file upload request "
            "and execute unauthorized commands directly on the server without needing a password."
        ),
        "jargon_buster": json.dumps([
            {"term": "RCE (Remote Code Execution)", "meaning": "The most dangerous type of bug: someone anywhere on the internet can run their own code on your computer."},
            {"term": "FPM (FastCGI Process Manager)", "meaning": "A built-in PHP background service that handles incoming web traffic quickly."},
            {"term": "CVE", "meaning": "Common Vulnerabilities and Exposures — an official catalog ID (like a case file number) given to security vulnerabilities."},
            {"term": "Use-After-Free", "meaning": "A computer memory error where a program tries to use information after throwing it in the digital trash bin."}
        ]),
        "crux_what_it_is": (
            "A critical use-after-free vulnerability in PHP-FPM's worker recycling logic "
            "(CVE-2024-8929) allows an attacker to achieve remote code execution by sending "
            "specially crafted multipart HTTP request bodies. The bug exists in PHP versions "
            "8.1.x < 8.1.31, 8.2.x < 8.2.24, and 8.3.x < 8.3.12."
        ),
        "crux_why_important": (
            "A working PoC was released on GitHub 12 hours ago by security researcher "
            "Marcus Hutchins, causing immediate community alarm. The affected FPM worker recycling "
            "code path is hit on virtually every PHP web server running multipart form uploads, "
            "making this trivially exploitable in default configurations."
        ),
        "crux_technical_details": json.dumps([
            "Root cause: `zend_mm_heap` segment is freed in `fpm_worker_free()` while a dangling pointer inside the request object still references it; a subsequent `malloc()` call can land on the same address.",
            "Trigger vector: Sending a multipart/form-data POST with a boundary value > 1024 bytes causes the recycling path to execute mid-request, corrupting the heap before response serialization.",
            "CVSS 3.1 score: 9.8 (Critical) — Network/Low/None/Un — impact: Confidentiality:High, Integrity:High, Availability:High.",
            "Patches landed in PHP 8.1.31, 8.2.24, 8.3.12 released today; distro packages (Debian, Ubuntu, RHEL, Alpine) still pending."
        ]),
        "crux_impact_dev": (
            "Upgrade PHP immediately: run `php --version` and compare to fixed versions "
            "(8.1.31 / 8.2.24 / 8.3.12). If you can't patch right now, add Nginx/Apache "
            "rules to reject multipart bodies with boundary strings > 512 bytes as a "
            "temporary WAF mitigation."
        ),
        "crux_impact_world": (
            "PHP powers roughly 77% of server-side web infrastructure. An exploitable "
            "RCE in FPM — the default SAPI for all modern PHP deployments — is effectively "
            "a mass-exploitation event waiting to happen. Expect widespread scanning within 24 hours."
        ),
        "full_text": """# PHP FPM CVE-2024-8929 — Technical Deep Dive

## Summary
A critical use-after-free vulnerability (CVE-2024-8929) in PHP-FPM's worker recycling subsystem
allows unauthenticated remote code execution via crafted multipart/form-data POST requests.

## Affected Versions
- PHP 8.1 < 8.1.31
- PHP 8.2 < 8.2.24
- PHP 8.3 < 8.3.12

## Plain-Language Explanation
Think of PHP workers like restaurant waiters. When a waiter finishes serving a table (a web request),
they clean up and reset. This bug occurs when a customer sends an abnormally long menu request,
confusing the waiter into throwing out a memory platter while the kitchen is still putting food on it.
A malicious customer can use that confusion to place their own custom orders.

## Mitigation
Update PHP to 8.1.31, 8.2.24, or 8.3.12 immediately.
""",
        "full_text_available": True,
        "llm_processed": True,
    },

    # ── 2. Rust Soundness Hole ───────────────────────────────────────────────
    {
        "source_url": "https://blog.rust-lang.org/2024/11/unsafe-transmute-soundness",
        "source_domain": "blog.rust-lang.org",
        "original_title": "Soundness Hole in std::mem::transmute with Generics Closed in Rust 1.82",
        "published_at": _dt(14),
        "hn_score": 621,
        "hn_comments": 445,
        "hn_item_id": 42079112,
        "clean_title": "Rust 1.82 Closes Soundness Hole: `transmute` with Lifetimes in Generic Contexts Could Bypass Borrow Checker",
        "simple_title": "Rust Closes a Safety Loophole That Could Have Caused Memory Crashes",
        "simple_badge": "🛡️ Core Language Bug Fix",
        "category": "bugs_cves",
        "tags": json.dumps(["#Rust", "#Soundness", "#MemorySafety", "#Compiler"]),
        "importance_badge": "⚡ Rust Soundness Fix — Depth: 9/10",
        "technical_depth_score": 9,
        "importance_score": 94.0,
        "is_daily_briefing": True,
        "plain_english_summary": (
            "Rust is beloved by developers because the compiler guarantees that your program will never crash "
            "from memory mistakes. Researchers found a sneaky loophole that bypassed Rust's digital safety guards. "
            "The Rust team released version 1.82 to close this gap."
        ),
        "jargon_buster": json.dumps([
            {"term": "Borrow Checker", "meaning": "Rust's built-in digital traffic cop that ensures multiple parts of a program don't edit or delete the same memory at the same time."},
            {"term": "Soundness Hole", "meaning": "A rare defect in a programming language where the compiler promises your code is 100% safe, but it actually isn't."},
            {"term": "Transmute", "meaning": "A dangerous command that forces the computer to treat one data type as another (like treating text as a number)."}
        ]),
        "crux_what_it_is": (
            "Rust 1.82 closes a soundness hole where `std::mem::transmute` used inside "
            "a generic function with lifetime parameters could bypass the borrow checker, "
            "allowing construction of arbitrarily long-lived references from shorter-lived "
            "ones — effectively enabling use-after-free in safe Rust code."
        ),
        "crux_why_important": (
            "This is a 'safe' code soundness violation — Rust's core promise broken without "
            "a single `unsafe` block in calling code. It was independently discovered and marked P-critical."
        ),
        "crux_technical_details": json.dumps([
            "Root cause: Compiler lifetime inference in `transmute` calls failed to propagate variance constraints in generic contexts.",
            "Affected pattern: Converting short-lived references into static references without compiler rejection.",
            "Fix: Added post-monomorphization MIR validation pass specifically for transmute intrinsics in Rust 1.82."
        ]),
        "crux_impact_dev": "Update your Rust compiler with `rustup update` to 1.82+.",
        "crux_impact_world": "Reaffirms Rust's reputation for taking safety violations with utmost seriousness.",
        "full_text": """# Rust 1.82 Soundness Fix

## Overview
Rust 1.82 patches an edge case where the compiler's borrow checker could be tricked into allowing
memory access after a variable was destroyed.

## Why This Matters
For 99.9% of developers, this simply means updating Rust (`rustup update`) ensures code remains rock-solid.
""",
        "full_text_available": True,
        "llm_processed": True,
    },

    # ── 3. Lazarus UEFI Bootkit ──────────────────────────────────────────────
    {
        "source_url": "https://securelist.com/lazarus-uefi-bootkit-analysis/114891/",
        "source_domain": "securelist.com",
        "original_title": "Lazarus Group's 'BlackDragon' UEFI Bootkit: Full Reverse Engineering Walkthrough",
        "published_at": _dt(18),
        "hn_score": 389,
        "hn_comments": 201,
        "hn_item_id": 42077443,
        "clean_title": "Lazarus Group 'BlackDragon' UEFI Bootkit Reverse-Engineered: Achieves Persistence Below OS via EFI Variable Hijacking",
        "simple_title": "Sophisticated Spy Malware Found Hiding Inside Computer Chips Before Windows Boots",
        "simple_badge": "🔬 Dangerous Spyware Discovered",
        "category": "rea",
        "tags": json.dumps(["#UEFI", "#Bootkit", "#Malware", "#ReverseEngineering"]),
        "importance_badge": "🔍 Nation-State Bootkit Dissected",
        "technical_depth_score": 10,
        "importance_score": 91.0,
        "is_daily_briefing": True,
        "plain_english_summary": (
            "Normally, if your computer gets a bad virus, formatting your hard drive and reinstalling Windows fixes it. "
            "This newly analyzed malware hides directly on the computer's motherboard chips. "
            "It boots before Windows or antivirus can start, and survives even if you throw away your hard drive."
        ),
        "jargon_buster": json.dumps([
            {"term": "UEFI / BIOS", "meaning": "The mini-operating system pre-installed on the motherboard that wakes up your hardware and starts Windows."},
            {"term": "Bootkit", "meaning": "Ultra-stealthy malware that infects the computer before the regular operating system loads."},
            {"term": "Reverse Engineering", "meaning": "Taking apart computer code line-by-line to understand how it was built, like an engineer disassembling a foreign jet engine."}
        ]),
        "crux_what_it_is": (
            "Kaspersky has published a full reverse-engineering breakdown of 'BlackDragon', "
            "a UEFI bootkit that plants malware into the pre-boot motherboard environment to survive full disk wipes."
        ),
        "crux_why_important": (
            "Only 5 in-the-wild UEFI bootkits have ever been documented. This proves nation-state "
            "attackers are actively deploying hardware-level persistence."
        ),
        "crux_technical_details": json.dumps([
            "Exploits vulnerable Lenovo EFI binaries to write malicious DXE drivers into the boot partition.",
            "Hooks EFI Boot Services to disable Windows Driver Signature Enforcement before the Windows kernel starts.",
            "Hides memory allocations in ACPI ranges that security scanners traditionally skip."
        ]),
        "crux_impact_dev": "Ensure Secure Boot is enforced in BIOS settings and update motherboard firmware regularly.",
        "crux_impact_world": "Pushes the industry toward hardware TPM attestation and firmware integrity verification.",
        "full_text": """# BlackDragon UEFI Bootkit Analysis

## Plain English Summary
Security analysts disassembled a rare malware strain that burrows into computer motherboard firmware.
Because it runs before Windows starts, it turns off security defenses invisibly.

## How to Protect Yourself
- Keep motherboard BIOS/firmware updated.
- Keep 'Secure Boot' enabled in UEFI settings.
""",
        "full_text_available": True,
        "llm_processed": True,
    },

    # ── 4. Aider Architect Mode ──────────────────────────────────────────────
    {
        "source_url": "https://simonwillison.net/2024/Nov/aider-architect-mode",
        "source_domain": "simonwillison.net",
        "original_title": "Aider's New Architect Mode: Separating Planning from Editing with Two LLMs",
        "published_at": _dt(10),
        "hn_score": 334,
        "hn_comments": 187,
        "hn_item_id": 42080221,
        "clean_title": "Aider v0.63 'Architect Mode': Uses a Strong LLM for Planning and a Cheaper Model for Code Edits, Cutting Costs 60%",
        "simple_title": "AI Coding Tool Now Uses Two AIs: A Smart One to Plan, and a Fast One to Write Code",
        "simple_badge": "🤖 AI Productivity Trick",
        "category": "applied_ai",
        "tags": json.dumps(["#Aider", "#CodingAgent", "#LLM", "#DevWorkflow"]),
        "importance_badge": "🤖 Aider Architect Mode — Real Workflow Win",
        "technical_depth_score": 8,
        "importance_score": 85.0,
        "is_daily_briefing": True,
        "plain_english_summary": (
            "Top-tier AI models (like Claude 3.5 Sonnet or OpenAI o1) are great at thinking but expensive. "
            "Aider now splits the job: the smart AI creates the step-by-step game plan, "
            "while a cheaper, lightning-fast AI types out the code edits — cutting your API bill by 60% without losing quality."
        ),
        "jargon_buster": json.dumps([
            {"term": "Coding Agent", "meaning": "An AI assistant that can inspect your code repository, make changes across multiple files, and run tests automatically."},
            {"term": "LLM (Large Language Model)", "meaning": "AI systems like ChatGPT, Claude, or Gemini trained to understand and generate human text and software code."},
            {"term": "API Cost / Tokens", "meaning": "The fee charged by AI providers per word/piece of code processed."}
        ]),
        "crux_what_it_is": (
            "Aider v0.63 introduces 'Architect Mode', pairing a reasoning-heavy LLM for architecture and planning "
            "with a lower-cost model for writing file diffs, achieving parity with frontier models at 60% lower cost."
        ),
        "crux_why_important": (
            "Solves the primary bottleneck of AI coding agents: high token costs and slow turnaround during multi-file edits."
        ),
        "crux_technical_details": json.dumps([
            "Architect model creates a structured implementation plan without emitting full code files.",
            "Editor model receives only the plan and targeted file slices, drastically minimizing prompt tokens.",
            "Matches o1-preview on SWE-bench at 42% of total token cost."
        ]),
        "crux_impact_dev": "Use `aider --architect o1-mini --model deepseek/deepseek-coder` for economical, high-accuracy refactoring.",
        "crux_impact_world": "Sets the design pattern for next-generation dual-agent developer tools.",
        "full_text": """# Aider Architect Mode: The Technical Breakdown

## Concept
Think of it like building a house: you hire an experienced Architect to draft the blueprints,
and skilled builders to lay the bricks. You don't pay the architect's hourly rate for stacking drywall!
""",
        "full_text_available": True,
        "llm_processed": True,
    },

    # ── 5. Freeze CLI Tool ──────────────────────────────────────────────────
    {
        "source_url": "https://github.com/charmbracelet/freeze",
        "source_domain": "github.com",
        "original_title": "Freeze — Generate beautiful images of code and terminal output",
        "published_at": _dt(22),
        "hn_score": 892,
        "hn_comments": 334,
        "hn_item_id": 42075001,
        "clean_title": "`freeze` by Charmbracelet: CLI Tool That Renders Code Snippets and Terminal Output as Production-Quality PNG/SVG Images",
        "simple_title": "New Command-Line Tool Turns Ugly Code Into Gorgeous Screenshot Cards",
        "simple_badge": "🛠️ Handy Developer Tool",
        "category": "dev_qol",
        "tags": json.dumps(["#CLI", "#Charmbracelet", "#Go", "#OpenSource"]),
        "importance_badge": "🔥 HN 892 pts — Dev QoL Gold",
        "technical_depth_score": 7,
        "importance_score": 88.0,
        "is_daily_briefing": True,
        "plain_english_summary": (
            "Developers often want to share pretty pictures of their code on Twitter, LinkedIn, or in documentation. "
            "Instead of manually cropping screenshots or uploading code to third-party websites, "
            "you can now type `freeze mycode.py` in your terminal to instantly generate high-resolution PNG or SVG images."
        ),
        "jargon_buster": json.dumps([
            {"term": "CLI (Command Line Interface)", "meaning": "The text terminal window where you run commands by typing words instead of clicking with a mouse."},
            {"term": "PNG / SVG", "meaning": "Standard image file formats. SVG images are vector graphics, meaning they stay crystal sharp at any zoom level."}
        ]),
        "crux_what_it_is": (
            "`freeze` is an open-source CLI utility from Charmbracelet that converts terminal output and source code files "
            "into crisp, styled PNG and SVG images with zero configuration."
        ),
        "crux_why_important": (
            "Over 890 upvotes on Hacker News because it replaces web-based screenshot tools with a scriptable, local CLI workflow."
        ),
        "crux_technical_details": json.dumps([
            "Syntax highlighting for 200+ languages powered by Chroma.",
            "Supports piping: `git diff | freeze -o diff.png`.",
            "Built with Go and Glamour/Lip Gloss terminal styling engines."
        ]),
        "crux_impact_dev": "Install with `brew install charmbracelet/tap/freeze` or `go install github.com/charmbracelet/freeze@latest`.",
        "crux_impact_world": "Elevates visual standards for open-source documentation and developer social posts.",
        "full_text": """# Freeze: Beautiful Terminal Screenshots
Run `freeze app.py -o image.png` to turn any code file into an elegant card with syntax highlighting.
""",
        "full_text_available": True,
        "llm_processed": True,
    },

    # ── 6. Meta's Tectonic Exabyte Storage ──────────────────────────────────
    {
        "source_url": "https://engineering.fb.com/2024/11/tectonic-exabyte-storage",
        "source_domain": "engineering.fb.com",
        "original_title": "Tectonic Exabyte: Petascale Metadata Service Powering Meta's Unified Storage",
        "published_at": _dt(30),
        "hn_score": 445,
        "hn_comments": 223,
        "hn_item_id": 42073889,
        "clean_title": "Meta's Tectonic Exabyte: Architecture of a Petascale Metadata Service Handling 1B+ File Operations/Day",
        "simple_title": "How Meta Built a Super-Fast Index to Track Billions of Photos Across Data Centers",
        "simple_badge": "🏗️ Massive Scale Engineering",
        "category": "architecture",
        "tags": json.dumps(["#DistributedSystems", "#Meta", "#Storage", "#ScaleDesign"]),
        "importance_badge": "🏗️ Exabyte-Scale Architecture — Depth: 9/10",
        "technical_depth_score": 9,
        "importance_score": 82.0,
        "is_daily_briefing": True,
        "plain_english_summary": (
            "When billions of users upload Reels and photos to Instagram, Facebook, and WhatsApp every day, "
            "the hardest part isn't storing the files — it's keeping track of where every single file is located. "
            "Meta shared the blueprint for their 'Tectonic' system, which handles over 1 billion lookups daily in under 10 milliseconds."
        ),
        "jargon_buster": json.dumps([
            {"term": "Exabyte", "meaning": "1 billion gigabytes. Enough storage to hold hundreds of millions of full HD movies."},
            {"term": "Metadata", "meaning": "Information about a file (name, size, timestamp, which hard drive holds it) rather than the image itself."},
            {"term": "p99 Latency", "meaning": "A speed benchmark measuring the slowest 1% of requests. Meta's system answers 99% of queries in under 8 milliseconds."}
        ]),
        "crux_what_it_is": (
            "Meta published the architecture of Tectonic Exabyte, their metadata service managing namespace and chunk "
            "mappings across exabyte-scale unified storage with sub-10ms p99 latency."
        ),
        "crux_why_important": (
            "Provides rare real-world engineering data on operating storage at true exabyte scale beyond the limits of HDFS or Ceph."
        ),
        "crux_technical_details": json.dumps([
            "Uses a custom primary-backup key-value layer on RocksDB rather than generic Raft consensus.",
            "Chunk-level erasure coding: RS(10,4) for warm data and RS(6,3) for cold archives.",
            "Two-tier cache: in-process LRU per server + dedicated distributed Memcached tier."
        ]),
        "crux_impact_dev": "Study how separating the metadata hot path from background garbage collection prevents lag spikes in large databases.",
        "crux_impact_world": "Will influence next-generation cloud and distributed file system architectures.",
        "full_text": """# Meta Tectonic Exabyte Deep Dive
Meta manages over 1 Exabyte of data with a specialized distributed metadata engine.
""",
        "full_text_available": True,
        "llm_processed": True,
    },

    # ── 7. glibc LPE Vulnerability ──────────────────────────────────────────
    {
        "source_url": "https://www.openwall.com/lists/oss-security/2024/11/glibc-srop",
        "source_domain": "openwall.com",
        "original_title": "glibc: SROP Gadget in __restore_rt Enables Privilege Escalation on All Linux Distros",
        "published_at": _dt(4),
        "hn_score": 712,
        "hn_comments": 389,
        "hn_item_id": 42082001,
        "clean_title": "glibc Sigreturn-Oriented Programming Gadget in `__restore_rt` Enables Local Privilege Escalation (CVE-2024-9184) — All Major Linux Distros Affected",
        "simple_title": "Critical Linux Flaw Lets Any Regular User Secretly Become the Super Admin",
        "simple_badge": "🚨 Dangerous Linux Zero-Day",
        "category": "bugs_cves",
        "tags": json.dumps(["#glibc", "#LPE", "#SROP", "#Linux"]),
        "importance_badge": "🚨 glibc LPE — Zero-Day Dropped",
        "technical_depth_score": 10,
        "importance_score": 99.0,
        "is_daily_briefing": True,
        "plain_english_summary": (
            "On Linux computers and servers, regular users have restricted accounts that prevent them from snooping "
            "on other people or installing spyware. A newly exposed flaw in Linux's core software library allows any "
            "ordinary user or rogue background app to instantly elevate themselves to full Administrator (Root) control."
        ),
        "jargon_buster": json.dumps([
            {"term": "glibc", "meaning": "The fundamental software foundation on virtually every Linux computer; almost all programs use it to communicate with the OS."},
            {"term": "Privilege Escalation (LPE)", "meaning": "When someone with low-level guest access finds a trick to grant themselves master super-admin rights."},
            {"term": "Zero-Day", "meaning": "A security vulnerability made public before software vendors have released a fix for it."}
        ]),
        "crux_what_it_is": (
            "A local privilege escalation vulnerability (CVE-2024-9184) in glibc's signal handling routines "
            "allows unprivileged attackers to gain root access via Sigreturn-Oriented Programming (SROP)."
        ),
        "crux_why_important": (
            "Affects all major Linux distributions (Ubuntu, Debian, Fedora, RHEL). A working public proof-of-concept exploit was released."
        ),
        "crux_technical_details": json.dumps([
            "Abuses `__restore_rt` gadget (mov $15, %eax; syscall) to forge ucontext_t signal frames.",
            "glibc 2.40 compile changes placed the gadget at predictable offsets, easing ASLR bypass.",
            "Confirmed working against setuid root binaries like `su` on Ubuntu 24.04."
        ]),
        "crux_impact_dev": "Update your Linux servers as soon as your distribution releases updated `libc6` or `glibc` packages.",
        "crux_impact_world": "Emergency out-of-band updates underway across every major Linux distribution.",
        "full_text": """# glibc CVE-2024-9184 Technical Details
All Linux administrators should monitor distro advisories for immediate glibc updates.
""",
        "full_text_available": True,
        "llm_processed": True,
    },

    # ── 8. SQLite WASM 1.0 ──────────────────────────────────────────────────
    {
        "source_url": "https://www.sqlite.org/2024/wasm-everywhere.html",
        "source_domain": "sqlite.org",
        "original_title": "SQLite Everywhere: The Wasm Build That's Redefining Client-Side Data",
        "published_at": _dt(36),
        "hn_score": 567,
        "hn_comments": 298,
        "hn_item_id": 42071445,
        "clean_title": "SQLite WASM 1.0: Official WebAssembly Port Enables Full SQLite in the Browser with OPFS Backend and Worker Thread Isolation",
        "simple_title": "World's Most Popular Database Can Now Run Directly Inside Your Web Browser",
        "simple_badge": "⚡ Faster Offline Web Apps",
        "category": "architecture",
        "tags": json.dumps(["#SQLite", "#WASM", "#Browser", "#LocalFirst"]),
        "importance_badge": "⚡ SQLite WASM 1.0 — Local-First Milestone",
        "technical_depth_score": 8,
        "importance_score": 83.0,
        "is_daily_briefing": False,
        "plain_english_summary": (
            "Normally, web applications have to send queries to a database located on a cloud server across the internet. "
            "With this official release, the entire SQLite database can run right inside your web browser (Chrome, Firefox, Safari). "
            "This lets apps work instantly and continue working even when you are completely offline."
        ),
        "jargon_buster": json.dumps([
            {"term": "WASM (WebAssembly)", "meaning": "A technology that allows fast, heavy software written in languages like C or Rust to run inside web browsers at near-native speed."},
            {"term": "Local-First", "meaning": "Apps designed to store your data on your personal device first, instead of forcing you to rely on an internet cloud connection."},
            {"term": "SQLite", "meaning": "The world's most widely used database engine, found in every iPhone, Android, and web browser."}
        ]),
        "crux_what_it_is": (
            "The official SQLite WebAssembly port reached 1.0 stable, bringing full ACID-compliant relational database "
            "capabilities directly to browser runtimes backed by Origin Private File System (OPFS)."
        ),
        "crux_why_important": (
            "Enables genuine local-first web applications with complex SQL queries and offline persistence without a remote server."
        ),
        "crux_technical_details": json.dumps([
            "Uses OPFS synchronous access handles in Web Workers for zero-latency disk I/O.",
            "Total bundle size is only 380KB gzipped including JavaScript glue.",
            "Full SQL feature set supported: WAL mode, FTS5 full-text search, and JSON functions."
        ]),
        "crux_impact_dev": "Install with `npm install @sqlite.org/sqlite-wasm` to build offline-ready web apps.",
        "crux_impact_world": "Accelerates the local-first software movement away from cloud-only architectures.",
        "full_text": """# SQLite WASM 1.0
SQLite now officially runs inside browsers with persistent disk storage.
""",
        "full_text_available": True,
        "llm_processed": True,
    },
]


async def seed_database(force_reseed: bool = False) -> int:
    """Populate database with seed articles. If force_reseed is True, refresh existing records."""
    await init_db()

    async with AsyncSessionLocal() as session:
        if force_reseed:
            await session.execute(delete(Article))
            await session.commit()
        else:
            result = await session.execute(select(Article).limit(1))
            if result.scalars().first():
                logger.info("Seed: DB already has data. Use force_reseed=True to refresh.")
                return 0

        inserted = 0
        for data in SEED_ARTICLES:
            try:
                article = Article(**data)
                session.add(article)
                inserted += 1
            except Exception as exc:
                logger.warning("Seed error: %s", exc)

        await session.commit()
        logger.info("Seed: inserted %d articles.", inserted)
        return inserted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count = asyncio.run(seed_database(force_reseed=True))
    print(f"Database successfully populated with {count} rich, beginner-friendly articles.")
