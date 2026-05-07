#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# reset.sh — Reset the database to a clean seeded state
#
# ⚠  This drops ALL tables (including analysis results, skills,
#    workflows, and patient memories) and re-seeds from fixtures.
#    Analysis results are NOT re-generated — that takes ~20 min.
#
# To rebuild everything including analysis: ./scripts/demo.sh
# To restore a previous snapshot:          ./scripts/restore.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

cd "$(dirname "$0")/.."

# Safety check — warn if analysis data exists
HAS_ANALYSIS=$(python3 -c "
import sqlite3, os
db = 'data/receptionist.db'
if not os.path.exists(db):
    print('no')
else:
    conn = sqlite3.connect(db)
    try:
        n = conn.execute('SELECT COUNT(*) FROM skills').fetchone()[0]
        print('yes' if n > 0 else 'no')
    except:
        print('no')
    conn.close()
" 2>/dev/null)

if [ "$HAS_ANALYSIS" = "yes" ] && [ "${1:-}" != "--force" ]; then
    echo "⚠  Database contains analysis results (skills, workflows, etc.)"
    echo "   These take ~20 min to regenerate."
    echo ""
    echo "   Options:"
    echo "     ./scripts/backup.sh         # save a snapshot first"
    echo "     ./scripts/reset.sh --force  # proceed anyway"
    echo ""
    read -p "   Continue? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
fi

echo "=== Resetting database ==="
python3 -m backend.seed.seed_data --reset
echo ""
echo "Database reset complete. Analysis results cleared."
echo "To restore analysis: ./scripts/restore.sh or ./scripts/demo.sh"
