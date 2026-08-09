# Holehe Email Scraper Parameters

## Input Parameters
These are the values passed to `scraper.run(params)`:

| Parameter | Type | Required | Example | Notes |
|-----------|------|----------|---------|-------|
| email | string | Yes | "user@example.com" | Target email address |
| onlyUsed | boolean | No | false | Show only sites where email is found |
| noColor | boolean | No | false | Disable colored output |
| noClear | boolean | No | false | Don't clear terminal before results |
| noPasswordRecovery | boolean | No | false | Skip password recovery attempts |
| csv | boolean | No | false | Output results as CSV |
| timeout | int | No | 10 | Max timeout per service check (seconds) |

## API Integration

### Holehe Modules (Services Checked)
Holehe checks ~123 different online services including:
- Social media: Twitter, Instagram, Snapchat, Facebook, Discord, etc.
- Email providers: Gmail, Outlook, etc.
- Productivity: Adobe, Office365, Dropbox, etc.
- Forums: Reddit, Stack Overflow, etc.
- Others: GitHub, Gravatar, LastPass, Spotify, etc.

Each module returns:
- Confirmation of email usage
- Metadata (if available from service)
- Status (found, not found, rate limited, error)

