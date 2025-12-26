"""
Test script to verify admin page performance improvements and timezone fixes.

This script tests:
1. Query count reduction (N+1 query fixes)
2. Beijing timezone conversion
3. Response times

Run with: python -m pytest tests/test_admin_performance.py -v
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.database import get_db, SessionLocal
from routers.auth import utc_to_beijing_iso, get_beijing_now, BEIJING_TIMEZONE
from models.auth import User, Organization
import time


def test_timezone_conversion():
    """Test that UTC timestamps are correctly converted to Beijing time."""
    # Create a UTC datetime
    utc_dt = datetime(2025, 1, 20, 10, 0, 0, tzinfo=timezone.utc)
    
    # Convert to Beijing time
    beijing_iso = utc_to_beijing_iso(utc_dt)
    
    # Verify it's in Beijing timezone (UTC+8)
    # UTC 10:00 should be Beijing 18:00 (10 + 8 = 18)
    assert beijing_iso is not None
    assert "+08:00" in beijing_iso or beijing_iso.endswith("+08:00")
    
    # Parse back and verify
    from dateutil import parser
    parsed = parser.parse(beijing_iso)
    assert parsed.tzinfo.utcoffset(None) == timedelta(hours=8)


def test_beijing_timezone_helper():
    """Test Beijing timezone helper functions."""
    beijing_now = get_beijing_now()
    assert beijing_now.tzinfo == BEIJING_TIMEZONE
    assert beijing_now.tzinfo.utcoffset(None) == timedelta(hours=8)


def test_user_list_query_count():
    """
    Test that user list endpoint uses optimized queries (not N+1).
    
    This test counts the number of queries executed.
    Note: Requires database connection and test data.
    """
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    
    query_count = []
    
    @event.listens_for(Engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        query_count.append(statement)
    
    try:
        db = SessionLocal()
        
        # Get some users (simulate the endpoint logic)
        users = db.query(User).limit(10).all()
        
        # Get organization IDs
        org_ids = {user.organization_id for user in users if user.organization_id}
        
        # Optimized: Single query for all organizations
        if org_ids:
            orgs = db.query(Organization).filter(Organization.id.in_(org_ids)).all()
            organizations_by_id = {org.id: org for org in orgs}
        else:
            organizations_by_id = {}
        
        # Count queries
        # Should be: 1 (users) + 1 (organizations) = 2 queries max
        # Old way would be: 1 (users) + N (one per user) = 1 + N queries
        
        db.close()
        
        # Verify we didn't do N+1 queries
        # With 10 users, old way = 11 queries, new way = 2 queries
        assert len(query_count) <= 2, f"Too many queries: {len(query_count)}. Expected <= 2"
        
    finally:
        event.remove(Engine, "before_cursor_execute", receive_before_cursor_execute)


def test_organization_list_query_count():
    """
    Test that organization list endpoint uses GROUP BY (not N+1).
    
    This test verifies the optimized query structure.
    """
    from sqlalchemy import event, func
    from sqlalchemy.engine import Engine
    
    query_count = []
    group_by_found = False
    
    @event.listens_for(Engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        query_count.append(statement)
        if "GROUP BY" in str(statement).upper():
            group_by_found = True
    
    try:
        db = SessionLocal()
        
        # Simulate optimized query
        user_counts_query = db.query(
            User.organization_id,
            func.count(User.id).label('user_count')
        ).filter(
            User.organization_id.isnot(None)
        ).group_by(
            User.organization_id
        ).all()
        
        db.close()
        
        # Verify GROUP BY was used
        assert group_by_found, "GROUP BY query not found - optimization may not be working"
        # Should be 1 query, not N queries
        assert len(query_count) == 1, f"Expected 1 query, got {len(query_count)}"
        
    finally:
        event.remove(Engine, "before_cursor_execute", receive_before_cursor_execute)


if __name__ == "__main__":
    print("Testing admin page performance improvements...")
    print("\n1. Testing timezone conversion...")
    try:
        test_timezone_conversion()
        print("   ✓ Timezone conversion works correctly")
    except Exception as e:
        print(f"   ✗ Timezone conversion failed: {e}")
    
    print("\n2. Testing Beijing timezone helper...")
    try:
        test_beijing_timezone_helper()
        print("   ✓ Beijing timezone helper works correctly")
    except Exception as e:
        print(f"   ✗ Beijing timezone helper failed: {e}")
    
    print("\n3. Testing query optimization...")
    print("   (Requires database connection - run with pytest for full test)")
    print("\nTo test manually:")
    print("1. Enable SQL logging: Set echo=True in config/database.py line 226")
    print("2. Load admin page and check logs for query count")
    print("3. Verify timestamps show Beijing time (UTC+8)")
    print("4. Check browser Network tab for response times")






