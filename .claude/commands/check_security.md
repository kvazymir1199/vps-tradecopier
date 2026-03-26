# /check-security - Security Check

Command for checking code for potential security issues.

## Usage

```
/check-security
```

## What Is Checked

### 1. Hardcoded Credentials

Search patterns:

```bash
grep -rn "password\s*=" Include/ Stage2.mq5
grep -rn "api_key\s*=" Include/ Stage2.mq5
grep -rn "secret\s*=" Include/ Stage2.mq5
grep -rn "token\s*=" Include/ Stage2.mq5
```

### 2. Sensitive Files

Check for presence in the repository:

```bash
# Should NOT be in git
find . -name "*.env" -o -name "credentials*" -o -name "*secret*"

# Check .gitignore
cat .gitignore | grep -E "(env|credential|secret|key)"
```

### 3. API Keys in Code

```bash
# Search for API key patterns
grep -rn "[A-Za-z0-9]{32,}" Include/ Stage2.mq5
grep -rn "sk_live_" Include/ Stage2.mq5  # Stripe live keys
grep -rn "pk_live_" Include/ Stage2.mq5  # Stripe public keys
```

### 4. Unsafe Operations

```bash
# Search for unsafe functions
grep -rn "Shell(" Include/ Stage2.mq5        # Command execution
grep -rn "WebRequest" Include/ Stage2.mq5    # HTTP requests
grep -rn "FileOpen" Include/ Stage2.mq5      # File operations
```

## Security Checklist

- [ ] No hardcoded passwords or keys
- [ ] `.gitignore` contains `.env`, `credentials*`, `*secret*`
- [ ] No API keys in source code
- [ ] WebRequest uses HTTPS
- [ ] FileOpen does not read system files
- [ ] Shell() is not used (or used safely)

## Recommendations

### Secret Storage

For MQL5, use:

1. **Configuration files** (not in git):
   ```cpp
   string ReadConfig(string key) {
      int handle = FileOpen("config.ini", FILE_READ|FILE_TXT|FILE_COMMON);
      // ...
   }
   ```

2. **Environment variables** (via external script):
   ```cpp
   input string InpApiKey = "";  // Passed at startup
   ```

### Secure WebRequest

```cpp
// GOOD: HTTPS
WebRequest("POST", "https://api.example.com/webhook", ...);

// BAD: HTTP
WebRequest("POST", "http://api.example.com/webhook", ...);
```

## Notes

- This check does not replace a full security audit
- For production systems, an external code review is recommended
- MQL5 has limited security capabilities compared to server-side languages
