#!/bin/bash
# Sync skills from ~/.claude/skills/ to agents/skills/
# Categorizes as LOCAL (Claude Code) or REMOTE (Modal.com)

SKILLS_SRC="$HOME/.claude/skills"
SKILLS_DST="/Users/nad/Library/CloudStorage/OneDrive-Personal/Agents/agents/skills"

# Create category file for tracking
CATEGORY_FILE="$SKILLS_DST/skill-categories.json"

echo "Starting skill sync..."

# REMOTE skills - require cloud compute (Modal.com deployment)
# Criteria: Heavy compute, external APIs, browser automation, media processing
REMOTE_SKILLS=(
    "ai-multimodal"      # GPU, Gemini API, media processing
    "media-processing"   # FFmpeg, ImageMagick, heavy compute
    "video-downloader"   # yt-dlp, bandwidth, storage
    "image-enhancer"     # Image processing
    "firebase-automation" # Firebase SDK, persistent connections
    "databases"          # Database connections
    "devops"             # Cloud CLI tools
    "shopify"            # Shopify API, OAuth
    "linkedin-automation" # Browser automation
    "tiktok-automation"   # Browser automation
    "fb-automation"       # Browser automation
    "fb-to-tiktok"        # Cross-platform automation
    "publer-automation"   # API integrations
    "payment-integration" # Payment APIs
)

# LOCAL skills - Claude Code extensions (no Modal needed)
# Criteria: Pure LLM guidance, local file ops, development workflows
LOCAL_SKILLS=(
    "planning"
    "research"
    "backend-development"
    "frontend-development"
    "mobile-development"
    "code-review"
    "debugging"
    "problem-solving"
    "internal-comms"
    "skill-creator"
    "worktree-manager"
    "mcp-management"
    "content-research-writer"
    "claude-code"
    "ai-artist"
    "canvas-design"
    "ui-styling"
    "ui-ux-pro-max"
    "frontend-design"
    "frontend-design-pro"
)

# HYBRID skills - work locally, optional Modal for scale
HYBRID_SKILLS=(
    "docx"
    "pdf"
    "pptx"
    "xlsx"
    "ooxml"
    "repomix"
    "sequential-thinking"
    "mcp-builder"
    "web-frameworks"
    "webapp-testing"
    "better-auth"
    "chrome-devtools"
)

# Function to check if skill is in array
contains() {
    local e match="$1"
    shift
    for e; do [[ "$e" == "$match" ]] && return 0; done
    return 1
}

# Function to get category
get_category() {
    local skill="$1"
    if contains "$skill" "${REMOTE_SKILLS[@]}"; then
        echo "remote"
    elif contains "$skill" "${LOCAL_SKILLS[@]}"; then
        echo "local"
    elif contains "$skill" "${HYBRID_SKILLS[@]}"; then
        echo "hybrid"
    else
        echo "uncategorized"
    fi
}

# Start JSON
echo '{' > "$CATEGORY_FILE"
echo '  "generated": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'",\n' >> "$CATEGORY_FILE"
echo '  "skills": {' >> "$CATEGORY_FILE"

first=true

# Sync each skill
for skill_dir in "$SKILLS_SRC"/*/; do
    skill_name=$(basename "$skill_dir")

    # Skip non-skill directories
    if [[ "$skill_name" == "references" ]] || \
       [[ "$skill_name" == "templates" ]] || \
       [[ "$skill_name" == "themes" ]] || \
       [[ "$skill_name" == "scripts" ]] || \
       [[ "$skill_name" == "examples" ]] || \
       [[ "$skill_name" == "common" ]] || \
       [[ "$skill_name" == "core" ]] || \
       [[ "$skill_name" == "reference" ]]; then
        continue
    fi

    # Check if SKILL.md exists
    if [[ ! -f "$skill_dir/SKILL.md" ]]; then
        continue
    fi

    category=$(get_category "$skill_name")

    # Only sync remote, local, and hybrid skills
    if [[ "$category" == "uncategorized" ]]; then
        continue
    fi

    echo "Syncing: $skill_name ($category)"

    # Create destination directory
    mkdir -p "$SKILLS_DST/$skill_name"

    # Copy SKILL.md as info.md
    cp "$skill_dir/SKILL.md" "$SKILLS_DST/$skill_name/info.md"

    # Copy scripts/ if exists (for remote/hybrid skills)
    if [[ -d "$skill_dir/scripts" ]] && [[ "$category" != "local" ]]; then
        cp -r "$skill_dir/scripts" "$SKILLS_DST/$skill_name/"
    fi

    # Add to JSON
    if [[ "$first" == "true" ]]; then
        first=false
    else
        echo ',' >> "$CATEGORY_FILE"
    fi

    has_scripts="false"
    [[ -d "$skill_dir/scripts" ]] && has_scripts="true"

    printf '    "%s": {"category": "%s", "has_scripts": %s}' "$skill_name" "$category" "$has_scripts" >> "$CATEGORY_FILE"
done

# Close JSON
echo '' >> "$CATEGORY_FILE"
echo '  }' >> "$CATEGORY_FILE"
echo '}' >> "$CATEGORY_FILE"

echo ""
echo "Sync complete!"
echo "Categories saved to: $CATEGORY_FILE"
