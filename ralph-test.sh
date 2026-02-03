#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPT_FILE="${SCRIPT_DIR}/ralph-prompt.md"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'

log() {
    echo -e "${BLUE}[ralph]${NC} $1"
}

log "================================================"
log "Running ralph test"
log "================================================"
log "Prompt file: $PROMPT_FILE"
log "================================================"
log "Running claude"
log "================================================"
claude --model opus -p "$PROMPT_FILE" --dangerously-skip-permissions
log "================================================"
log "Ralph test completed"
log "================================================"
