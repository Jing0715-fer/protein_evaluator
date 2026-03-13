#!/bin/bash

# Protein Evaluator Monitor Daemon
# Runs every 30 minutes to check project status

LOG_FILE="/Users/lijing/clawd/memory/protein-evaluator-check.log"
DAILY_REPORT="/Users/lijing/clawd/memory/protein-evaluator-daily-report.md"
PROJECT_DIR="/Users/lijing/literature_agent-V2-claude/protein_evaluator"
HEARTBEAT_FILE="$PROJECT_DIR/HEARTBEAT.md"

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M GMT+8')] $1" >> "$LOG_FILE"
}

# Function to check project status
check_project_status() {
    log_message "=== Starting Project Status Check ==="
    
    cd "$PROJECT_DIR" || exit 1
    
    # Check git status
    log_message "Git Status:"
    git status --short >> "$LOG_FILE" 2>&1
    
    # Check current branch
    CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
    log_message "Current Branch: $CURRENT_BRANCH"
    
    # Check recent commits
    log_message "Recent Commits:"
    git log --oneline -5 >> "$LOG_FILE" 2>&1
    
    # Run tests
    log_message "Running tests..."
    if python3 -m pytest tests/ -v --tb=short >> "$LOG_FILE" 2>&1; then
        log_message "TEST_STATUS: PASSED"
    else
        log_message "TEST_STATUS: FAILED"
    fi
    
    # Check for uncommitted changes
    UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    if [ "$UNCOMMITTED" -gt 0 ]; then
        log_message "WARNING: $UNCOMMITTED uncommitted file(s) detected"
    else
        log_message "STATUS: No uncommitted changes"
    fi
    
    log_message "=== Project Status Check Complete ==="
    log_message ""
}

# Function to analyze task progress
analyze_task_progress() {
    log_message "=== Analyzing Task Progress ==="
    
    if [ -f "$HEARTBEAT_FILE" ]; then
        log_message "Reading HEARTBEAT.md:"
        cat "$HEARTBEAT_FILE" >> "$LOG_FILE"
    else
        log_message "WARNING: HEARTBEAT.md not found"
    fi
    
    log_message "=== Task Progress Analysis Complete ==="
    log_message ""
}

# Function to generate daily report (runs at 9:00 AM)
generate_daily_report() {
    log_message "=== Generating Daily Report ==="
    
    cd "$PROJECT_DIR" || exit 1
    
    # Get current date
    REPORT_DATE=$(date '+%Y-%m-%d')
    
    # Start report
    cat > "$DAILY_REPORT" << EOF
# Protein Evaluator Daily Report
Generated: $REPORT_DATE $(date '+%H:%M GMT+8')

---

## Current Phase Status

### Phase 2.1 - 多序列比对功能
EOF
    
    # Check task status from heartbeat
    if [ -f "$HEARTBEAT_FILE" ]; then
        echo "Active Task:" >> "$DAILY_REPORT"
        grep -E "^\- \*\*" "$HEARTBEAT_FILE" >> "$DAILY_REPORT" 2>/dev/null || echo "- No active task found" >> "$DAILY_REPORT"
    fi
    
    # Test summary
    echo "" >> "$DAILY_REPORT"
    echo "## Test Status Summary" >> "$DAILY_REPORT"
    if python3 -m pytest tests/ --collect-only -q >> "$LOG_FILE" 2>&1; then
        TEST_COUNT=$(python3 -m pytest tests/ --collect-only -q 2>/dev/null | tail -1)
        echo "- Tests Collected: $TEST_COUNT" >> "$DAILY_REPORT"
    else
        echo "- Test collection failed" >> "$DAILY_REPORT"
    fi
    
    # Recent activity
    echo "" >> "$DAILY_REPORT"
    echo "## Recent Git Activity" >> "$DAILY_REPORT"
    git log --oneline -10 >> "$DAILY_REPORT" 2>&1
    
    # Recommendations section
    echo "" >> "$DAILY_REPORT"
    echo "## Recommendations" >> "$DAILY_REPORT"
    echo "- Continue with Phase 2.1 implementation" >> "$DAILY_REPORT"
    echo "- Ensure test coverage remains above 80%" >> "$DAILY_REPORT"
    echo "- Review and commit any completed work" >> "$DAILY_REPORT"
    
    log_message "Daily report generated: $DAILY_REPORT"
    log_message "=== Daily Report Complete ==="
    log_message ""
}

# Main execution
log_message "Protein Evaluator Monitor Daemon Started"
log_message "Project Directory: $PROJECT_DIR"

# Check if daily report should be generated (between 9:00-9:30 AM)
CURRENT_HOUR=$(date '+%H')
CURRENT_MIN=$(date '+%M')
if [ "$CURRENT_HOUR" = "09" ] && [ "$CURRENT_MIN" -lt "30" ]; then
    log_message "Scheduled daily report time detected"
    generate_daily_report
fi

# Run status checks
check_project_status
analyze_task_progress

# Check for task completion markers
if grep -q "TASK_COMPLETE" "$HEARTBEAT_FILE" 2>/dev/null; then
    log_message "TASK_COMPLETE marker detected in HEARTBEAT.md"
fi

# Check for decision requests
if grep -q "NEED_DECISION" "$HEARTBEAT_FILE" 2>/dev/null; then
    log_message "NEED_DECISION marker detected in HEARTBEAT.md - user action required"
fi

log_message "Monitor cycle complete. Next check in 30 minutes."
