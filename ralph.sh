#!/usr/bin/env bash
#
# ralph.sh - Automated feature development loop
#
# Calls Claude Code with a prompt to implement the next feature set from the PRD,
# verify acceptance criteria, and update progress.
#
# Usage:
#   ./ralph.sh           # Run once (default)
#   ./ralph.sh 3         # Run 3 iterations
#   ./ralph.sh -n 5      # Run 5 iterations
#   ./ralph.sh --dry-run # Show what would be done without running
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPT_FILE="${SCRIPT_DIR}/ralph-prompt.md"
LOG_DIR="${SCRIPT_DIR}/.ralph-logs"
ITERATIONS=1
DRY_RUN=false
MODEL="sonnet"  # sonnet for speed, opus for complex work

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[ralph]${NC} $1"
}

error() {
    echo -e "${RED}[ralph ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[ralph]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[ralph]${NC} $1"
}

usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] [ITERATIONS]

Automated feature development loop using Claude Code.

Options:
    -n, --iterations N    Number of iterations to run (default: 1)
    -m, --model MODEL     Model to use: sonnet (default, faster) or opus (complex work)
    -d, --dry-run         Show what would be done without running
    -p, --prompt FILE     Use custom prompt file (default: ralph-prompt.md)
    -h, --help            Show this help message

Examples:
    $(basename "$0")              # Run once with sonnet
    $(basename "$0") 3            # Run 3 iterations
    $(basename "$0") -n 5         # Run 5 iterations
    $(basename "$0") -m opus      # Use opus for complex features
    $(basename "$0") --dry-run    # Preview without running
EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--iterations)
            ITERATIONS="$2"
            shift 2
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -p|--prompt)
            PROMPT_FILE="$2"
            shift 2
            ;;
        -m|--model)
            MODEL="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        [0-9]*)
            ITERATIONS="$1"
            shift
            ;;
        *)
            error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Validate iterations
if ! [[ "$ITERATIONS" =~ ^[0-9]+$ ]] || [[ "$ITERATIONS" -lt 1 ]]; then
    error "Iterations must be a positive integer"
    exit 1
fi

# Check prerequisites
if ! command -v claude &> /dev/null; then
    error "Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
    exit 1
fi

if [[ ! -f "$PROMPT_FILE" ]]; then
    error "Prompt file not found: $PROMPT_FILE"
    exit 1
fi

if [[ ! -f "${SCRIPT_DIR}/PRD.md" ]]; then
    error "PRD.md not found in ${SCRIPT_DIR}"
    exit 1
fi

# Create log directory
mkdir -p "$LOG_DIR"

# Count remaining tasks in PRD
count_remaining() {
    grep -c '^\- \[ \]' "${SCRIPT_DIR}/PRD.md" 2>/dev/null || echo "0"
}

# Count completed tasks in PRD
count_completed() {
    grep -c '^\- \[x\]' "${SCRIPT_DIR}/PRD.md" 2>/dev/null || echo "0"
}

# Main execution
main() {
    local start_time
    local end_time
    local duration

    log "Starting ralph automation"
    log "Prompt file: $PROMPT_FILE"
    log "Model: $MODEL"
    log "Iterations: $ITERATIONS"
    log "Working directory: $SCRIPT_DIR"

    local initial_remaining
    initial_remaining=$(count_remaining)
    local initial_completed
    initial_completed=$(count_completed)

    log "PRD Status: ${initial_completed} completed, ${initial_remaining} remaining"

    if [[ "$DRY_RUN" == true ]]; then
        warn "DRY RUN - would execute:"
        echo "  claude --print \"$(head -5 "$PROMPT_FILE")...\""
        exit 0
    fi

    for i in $(seq 1 "$ITERATIONS"); do
        log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log "Iteration $i of $ITERATIONS"
        log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        local remaining
        remaining=$(count_remaining)

        if [[ "$remaining" -eq 0 ]]; then
            success "All PRD items completed!"
            break
        fi

        log "Remaining items: $remaining"

        # Create log file for this iteration
        local log_file="${LOG_DIR}/ralph-$(date +%Y%m%d-%H%M%S)-iter${i}.log"

        start_time=$(date +%s)

        # Read prompt and execute claude
        local prompt
        prompt=$(cat "$PROMPT_FILE")

        log "Executing Claude Code..."

        # Run claude with the prompt, allow it to make changes
        # -p for non-interactive prompt mode
        # --dangerously-skip-permissions to bypass permission checks
        if claude -p "$prompt" \
            --dangerously-skip-permissions \
            --model "$MODEL" \
            2>&1 | tee "$log_file"; then
            success "Iteration $i completed"
        else
            local exit_code=$?
            error "Iteration $i failed with exit code $exit_code"
            warn "Check log: $log_file"
            # Continue to next iteration rather than failing entirely
        fi

        end_time=$(date +%s)
        duration=$((end_time - start_time))

        log "Iteration $i took ${duration}s"

        # Show progress
        local new_remaining
        new_remaining=$(count_remaining)
        local new_completed
        new_completed=$(count_completed)
        local items_done=$((initial_remaining - new_remaining))

        log "Progress: ${new_completed} completed (+$((new_completed - initial_completed))), ${new_remaining} remaining"

        # Brief pause between iterations to avoid rate limits
        if [[ $i -lt $ITERATIONS ]] && [[ "$new_remaining" -gt 0 ]]; then
            log "Pausing 5s before next iteration..."
            sleep 5
        fi
    done

    # Final summary
    echo
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    success "Ralph automation complete"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    local final_remaining
    final_remaining=$(count_remaining)
    local final_completed
    final_completed=$(count_completed)

    log "Final PRD Status:"
    log "  Completed: ${final_completed} (+$((final_completed - initial_completed)))"
    log "  Remaining: ${final_remaining}"
    log "Logs: ${LOG_DIR}/"
}

main "$@"
