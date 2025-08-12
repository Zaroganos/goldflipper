# Goldflipper Developer Guide

## Recent Bug Fixes and Improvements

### WEM Module Fixes (2025-06-23)

#### Fixed Price Source Bug
**Problem**: WEM calculations were showing incorrect stock prices (e.g., $305.95 for COIN instead of expected $308.38).

**Root Cause**: 
- WEM was making live API calls instead of using cached Friday close prices
- Orphaned `market_data.source` reference causing runtime errors

**Solution**:
- Modified `calculate_expected_move()` to ALWAYS use previous Friday close prices
- Fixed the source reference to use proper cache key
- Added extensive logging to confirm WEM never uses live prices

**Code Changes**: 
```python
# BEFORE (incorrect)
price = manager.get_stock_price(symbol)  # Live API call

# AFTER (correct)  
current_price = _get_previous_friday_close_price(symbol, previous_friday_date)
logger.info(f"WEM calculation using previous Friday close (NEVER live API)")
```

#### Improved Number Formatting
**Problem**: WEM table displayed too many digits and inconsistent decimal places.

**Solution**: 
- Added `max_digits` parameter (default 5) to limit display width
- Always show minimum 2 decimal places for consistency
- Use scientific notation for numbers exceeding `max_digits`
- Added user controls in sidebar for both `sig_figs` and `max_digits`

**Implementation**:
```python
def format_number(x, col_name, max_digits=5):
    """Format numbers with max digits and minimum 2 decimal places"""
    if abs(num_val) >= 10**(max_digits):
        return f"{num_val:.2e}"  # Scientific notation
    else:
        return f"{num_val:.2f}"  # Always 2 decimal places
```

#### Fixed Delta 16+/- Validation Timing
**Problem**: Delta 16+/- validation was always "off" regardless of user settings.

**Root Cause**: Validation config was created AFTER the "Update WEM Data" button in sidebar execution order.

**Solution**:
- Moved validation controls to top of sidebar (before any buttons)
- Added debug logging to track validation config availability
- Ensured validation config exists in `st.session_state` before calculations

**Code Changes**:
```python
# BEFORE (wrong order)
# Update WEM Data button
# ... other controls ...
# Delta 16 Validation controls (config created here)

# AFTER (correct order)  
# Delta 16 Validation controls (config created first)
# Update WEM Data button (uses existing config)
```

#### Key Takeaways for Developers
1. **WEM Design Principle**: WEM calculations must ALWAYS use previous Friday close prices, never live market data
2. **Streamlit State Management**: UI controls that create config must come before buttons that use that config
3. **Number Formatting**: Consider both display constraints and user experience when formatting financial data
4. **Validation Systems**: Timing of config creation is critical in Streamlit apps

## Database Development Guide

### Overview
The Goldflipper database system uses DuckDB as its primary database engine, accessed through SQLAlchemy ORM. This guide covers development practices, patterns, and common tasks.

### Getting Started

#### Environment Setup
1. Install dependencies:
```bash
uv sync
```

2. Set up environment variables:
```bash
export GOLDFLIPPER_DATA_DIR=/path/to/data
export GOLDFLIPPER_DB_PATH=/path/to/db
export GOLDFLIPPER_DB_POOL_SIZE=5
export GOLDFLIPPER_DB_TIMEOUT=30
export GOLDFLIPPER_LOG_LEVEL=INFO
```

3. Initialize database:
```python
from goldflipper.database import init_db
init_db()
```

### Development Patterns

#### Repository Pattern
We use the repository pattern to abstract database operations:

```python
# BAD - Direct database access
with get_db_connection() as session:
    plays = session.query(Play).filter(Play.status == 'open').all()

# GOOD - Using repository
with get_db_connection() as session:
    repo = PlayRepository(session)
    plays = repo.get_by_status('open')
```

#### Error Handling
Always use proper error handling:

```python
try:
    with get_db_connection() as session:
        repo = PlayRepository(session)
        play = repo.create(play_data)
except SQLAlchemyError as e:
    logger.error(f"Database error: {e}")
    # Handle appropriately
    raise
```

#### Transaction Management
Use context managers for automatic transaction handling:

```python
# Transaction automatically handled
with get_db_connection() as session:
    repo = PlayRepository(session)
    play = repo.create(play_data)
    history_repo = PlayStatusHistoryRepository(session)
    history_repo.create(history_data)
    # Commit happens automatically if no errors
    # Rollback happens automatically on error
```

### Adding New Features

#### Adding a New Model
1. Create model in `models.py`:
```python
class NewModel(Base):
    __tablename__ = 'new_models'
    
    id = Column(SQLUUID, primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    # ... other fields
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'name': self.name
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NewModel':
        if 'id' in data:
            data['id'] = UUID(data['id'])
        return cls(**data)
```

2. Create repository in `repositories.py`:
```python
class NewModelRepository(BaseRepository):
    def __init__(self, session: Session):
        super().__init__(session)
        self.model_class = NewModel
    
    def custom_query(self) -> List[NewModel]:
        try:
            return self.session.query(NewModel).filter(...).all()
        except SQLAlchemyError as e:
            logger.error(f"Error in custom query: {e}")
            raise
```

3. Update `__init__.py`:
```python
from .models import NewModel
from .repositories import NewModelRepository

__all__ += ['NewModel', 'NewModelRepository']
```

#### Adding Database Migrations
1. Create migration script in `migrations/`:
```python
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'new_table',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('new_table')
```

### Testing

#### Unit Tests
Use pytest for testing:

```python
def test_play_repository():
    with get_db_connection() as session:
        repo = PlayRepository(session)
        
        # Test creation
        play = repo.create({
            'play_name': 'Test Play',
            'symbol': 'SPY',
            # ... other required fields
        })
        assert play.play_name == 'Test Play'
        
        # Test query
        plays = repo.get_by_status('new')
        assert len(plays) > 0
```

#### Integration Tests
Test full workflows:

```python
def test_play_workflow():
    with get_db_connection() as session:
        # Create repositories
        play_repo = PlayRepository(session)
        history_repo = PlayStatusHistoryRepository(session)
        trade_repo = TradeLogRepository(session)
        
        # Create play
        play = play_repo.create(play_data)
        
        # Update status
        play = play_repo.update_status(play.play_id, 'open')
        
        # Verify history
        history = history_repo.get_latest_status(play.play_id)
        assert history.status == 'open'
```

### Performance Optimization

#### Query Optimization
- Use specific queries instead of loading full objects
- Add indexes for frequently queried fields
- Use bulk operations for multiple records

```python
# BAD - Loading full objects
plays = repo.get_all()
symbols = [play.symbol for play in plays]

# GOOD - Specific query
symbols = session.query(Play.symbol).distinct().all()
```

#### Connection Pool Management
Configure pool size based on workload:

```python
# High concurrency settings
export GOLDFLIPPER_DB_POOL_SIZE=20
export GOLDFLIPPER_DB_TIMEOUT=60
```

### Troubleshooting

#### Common Issues

1. Connection Errors
```python
# Check connection
try:
    with get_db_connection() as session:
        session.execute("SELECT 1")
except SQLAlchemyError as e:
    logger.error(f"Connection test failed: {e}")
```

2. Migration Issues
```python
# Reset database (careful!)
init_db(force=True)

# Verify schema
with get_db_connection() as session:
    Base.metadata.create_all(session.bind)
```

3. Performance Issues
```python
# Enable SQL logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Profile queries
with get_db_connection() as session:
    from sqlalchemy import event
    
    @event.listens_for(session, 'after_cursor_execute')
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        print(f"Query took: {context.duration}")
``` 