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
MODEL="sonnet"  # sonnet for speed, opus for complex work

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
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
    -p, --prompt FILE     Use custom prompt file (default: ralph-prompt.md)
    -h, --help            Show this help message

Examples:
    $(basename "$0")              # Run once with sonnet
    $(basename "$0") 3            # Run 3 iterations
    $(basename "$0") -n 5         # Run 5 iterations
    $(basename "$0") -m opus      # Use opus for complex features
EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--iterations)
            if [[ -z "${2:-}" ]]; then
                error "Option $1 requires an argument"
                exit 1
            fi
            ITERATIONS="$2"
            shift 2
            ;;
        -p|--prompt)
            if [[ -z "${2:-}" ]]; then
                error "Option $1 requires an argument"
                exit 1
            fi
            PROMPT_FILE="$2"
            shift 2
            ;;
        -m|--model)
            if [[ -z "${2:-}" ]]; then
                error "Option $1 requires an argument"
                exit 1
            fi
            MODEL="$2"
            if [[ "$MODEL" != "sonnet" && "$MODEL" != "opus" ]]; then
                error "Invalid model: $MODEL (must be 'sonnet' or 'opus')"
                exit 1
            fi
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

if ! command -v jq &> /dev/null; then
    error "jq not found. Install with: brew install jq"
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

    for i in $(seq 1 "$ITERATIONS"); do
        log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log "Iteration $i of $ITERATIONS"
        log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        local remaining
        remaining=$(count_remaining)
        local completed_before
        completed_before=$(count_completed)

        if [[ "$remaining" -eq 0 ]]; then
            success "All PRD items completed!"
            break
        fi

        log "Remaining items: $remaining"

        # Create log file for this iteration
        local log_file="${LOG_DIR}/ralph-$(date +%Y%m%d-%H%M%S)-iter${i}.log"
        touch "$log_file"
        start_time=$(date +%s)

        # Read prompt and execute claude
        local prompt
        prompt=$(cat "$PROMPT_FILE")

        log "Executing Claude Code..."
        log "Log file: $log_file"

        echo ""
        echo -e "${MAGENTA}${BOLD}╔═══════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${MAGENTA}${BOLD}║  🤖 CLAUDE OUTPUT START                                           ║${NC}"
        echo -e "${MAGENTA}${BOLD}╚═══════════════════════════════════════════════════════════════════╝${NC}"
        echo ""

        # Run claude with the prompt, allow it to make changes
        # -p for non-interactive prompt mode
        # --dangerously-skip-permissions to bypass permission checks
        #
        # Temporarily disable errexit to capture exit code properly.
        local exit_code=0
        set +e

        claude -p "$prompt" --dangerously-skip-permissions --model "$MODEL" &
        CLAUDE_PID=$!

        log "Started claude with PID: $CLAUDE_PID"
        sleep 2
        CLAUDE_LOG_DIR="$HOME/.claude/projects/$(echo "$SCRIPT_DIR" | tr '/' '-')"
        CLAUDE_LOG_FILE=$(ls -t "$CLAUDE_LOG_DIR"/*.jsonl 2>/dev/null | head -1)

        if [ -z "$CLAUDE_LOG_FILE" ]; then
            warn "No log file found in $CLAUDE_LOG_DIR"
            wait $CLAUDE_PID
            exit_code=$?
        else
            (
                tail -f "$CLAUDE_LOG_FILE" | \
                jq --unbuffered -r 'select(.description != null) | .description' | \
                while IFS= read -r line; do
                    log "$line"
                    echo "$line" >> "$log_file"
                done
            ) &
            TAIL_PID=$!
            wait $CLAUDE_PID
            exit_code=$?
            kill $TAIL_PID 2>/dev/null
        fi

        log "Claude exited with code: $exit_code"
        # Show final output
        echo ""
        cat "$log_file"

        set -e

        echo ""
        echo -e "${MAGENTA}${BOLD}╔═══════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${MAGENTA}${BOLD}║  🤖 CLAUDE OUTPUT END                                             ║${NC}"
        echo -e "${MAGENTA}${BOLD}╚═══════════════════════════════════════════════════════════════════╝${NC}"
        echo ""

        if [[ "$exit_code" -eq 0 ]]; then
            success "Iteration $i completed"
        else
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
        local iteration_progress=$((new_completed - completed_before))

        log "Progress: ${new_completed} completed (+$((new_completed - initial_completed))), ${new_remaining} remaining"

        # Warn if no progress was made this iteration
        if [[ "$iteration_progress" -eq 0 ]] && [[ "$exit_code" -eq 0 ]]; then
            warn "No PRD items were completed this iteration"
            warn "Claude may be stuck or the task may be too complex"
        fi

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
