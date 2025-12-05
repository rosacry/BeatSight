# BeatSight Discord Server Setup Guide

## Server Structure

### Categories & Channels

```
📢 ANNOUNCEMENTS
├── #announcements        (read-only, release notes, major updates)
├── #changelog           (read-only, automated from GitHub releases)
└── #roadmap             (read-only, upcoming features)

💬 COMMUNITY
├── #general             (main chat)
├── #introductions       (new member intros)
├── #show-and-tell       (share your drumming progress)
└── #off-topic           (non-BeatSight chat)

🎵 BEATSIGHT
├── #support             (help with the app)
├── #feature-requests    (suggest new features)
├── #bug-reports         (report issues)
└── #beatmap-sharing     (share custom beatmaps)

🔧 DEVELOPMENT
├── #dev-chat            (development discussion)
├── #github-feed         (automated GitHub notifications)
├── #api-discussion      (API/integration questions)
└── #contributors        (for verified contributors)

🎓 LEARNING
├── #beginner-tips       (tips for new drummers)
├── #technique-discussion (discuss drumming techniques)
└── #resources           (tutorials, courses, links)
```

## Roles

### Staff Roles
- `@Admin` - Full server management
- `@Moderator` - Can manage messages, timeout users
- `@Developer` - BeatSight development team

### Community Roles
- `@Contributor` - Users who have contributed corrections (auto-assigned via bot)
- `@Verifier` - Trusted community verifiers
- `@Beta Tester` - Access to beta features
- `@Pro User` - Paid subscribers

### Karma-Based Roles (auto-assigned)
- `@Newcomer` - 0-99 karma
- `@Regular` - 100-499 karma
- `@Veteran` - 500-999 karma
- `@Expert` - 1000+ karma

## Bot Configuration

### Required Bots

#### 1. GitHub Bot (Webhooks)
Set up GitHub webhooks to post to `#github-feed`:
- Repository: `rosacry/BeatSight`
- Events: Push, Pull Request, Release, Issues
- Webhook URL: `https://discord.com/api/webhooks/YOUR_WEBHOOK_ID`

#### 2. MEE6 or Carl-bot (Moderation)
- Auto-moderation (spam, links, excessive caps)
- Welcome messages
- Role assignment commands

#### 3. Custom BeatSight Bot (Optional Future)
Integration with BeatSight API:
- `/link` - Link Discord account to BeatSight account
- `/karma` - Check karma and stats
- `/contributions` - View contribution count
- Automatic role sync based on karma/verifier status

## Server Settings

### Verification Level
- Medium (must have verified email)

### Default Permissions
- Everyone can read #announcements, #changelog, #roadmap
- Everyone can post in community channels
- Only verified roles can post in #dev-chat

### Slow Mode
- #support: 30 seconds
- #bug-reports: 60 seconds
- #feature-requests: 60 seconds

## Welcome Message Template

```
👋 Welcome to the BeatSight Discord, {user}!

**BeatSight** is an AI-powered drum transcription tool that transforms any song into visual drum notation for practice.

🎯 **Quick Links**
• Website: https://beatsight.app
• Documentation: https://docs.beatsight.app
• GitHub: https://github.com/rosacry/BeatSight

📋 **Getting Started**
1. Read the rules in #rules
2. Introduce yourself in #introductions
3. Ask questions in #support
4. Share your progress in #show-and-tell

🎵 **Have fun drumming!**
```

## Invite Link Settings
- Max uses: Unlimited
- Expiry: Never
- Grants: `@everyone` role only

## Moderation Rules Template

```
# BeatSight Discord Rules

1. **Be Respectful** - Treat everyone with respect. No harassment, hate speech, or discrimination.

2. **Stay On Topic** - Keep discussions relevant to the channel topic.

3. **No Spam** - No excessive posting, self-promotion, or advertising without permission.

4. **No Piracy** - Do not share pirated music or software.

5. **English Only** - Please use English in public channels for moderation purposes.

6. **No NSFW Content** - Keep all content appropriate for all ages.

7. **Report Issues** - Use the proper channels for bug reports and feature requests.

8. **Have Fun** - We're here to help each other become better drummers!

Violations may result in warnings, timeouts, or bans at moderator discretion.
```
