# Goldflipper Database API Reference

## Overview
The Goldflipper database package provides a robust data persistence layer using DuckDB and SQLAlchemy ORM. This document outlines the available models, repositories, and utilities for database operations.

## Models

### Play
The core model representing an options trading play.

```python
from goldflipper.database.models import Play

# Create a new play
play = Play(
    play_name="SPY Weekly Put",
    symbol="SPY",
    trade_type="PUT",
    strike_price=400.0,
    expiration_date=datetime(2024, 3, 28),
    contracts=1,
    status="new",
    play_class="SIMPLE"
)
```

Attributes:
- `play_id: UUID` - Unique identifier
- `play_name: str` - Human-readable name
- `symbol: str` - Trading symbol
- `trade_type: str` - 'CALL' or 'PUT'
- `strike_price: float` - Option strike price
- `expiration_date: datetime` - Option expiration
- `contracts: int` - Number of contracts
- `status: str` - Current status ('new', 'open', 'closed', 'expired')
- `play_class: str` - Play type ('SIMPLE', 'OCO', 'OTO')
- Additional fields for entry/exit conditions

### PlayStatusHistory
Tracks status changes and order states for plays.

```python
from goldflipper.database.models import PlayStatusHistory

# Record status change
history = PlayStatusHistory(
    play_id=play.play_id,
    status="open",
    order_id="abc123",
    position_exists=True
)
```

Attributes:
- `history_id: UUID` - Unique identifier
- `play_id: UUID` - Reference to play
- `status: str` - Status value
- `order_id: str` - Associated order ID
- `position_exists: bool` - Position state
- Additional fields for order tracking

### TradeLog
Records trade execution details and P/L.

```python
from goldflipper.database.models import TradeLog

# Log a trade
trade = TradeLog(
    play_id=play.play_id,
    datetime_open=datetime.now(),
    price_open=405.0,
    premium_open=2.50,
    delta_open=0.3,
    theta_open=-0.15
)
```

Attributes:
- `trade_id: UUID` - Unique identifier
- `play_id: UUID` - Reference to play
- `datetime_open/close: datetime` - Trade timestamps
- `price_open/close: float` - Stock prices
- `premium_open/close: float` - Option premiums
- Additional fields for Greeks and P/L

### Analytics
Stores trading analytics and performance metrics.

```python
from goldflipper.database.models import Analytics

# Record a metric
metric = Analytics(
    category="performance",
    metric="win_rate",
    value=0.65,
    meta_data={'timeframe': 'daily', 'strategy': 'momentum'}
)
```

Attributes:
- `analytics_id: UUID` - Unique identifier
- `category: str` - Metric category
- `metric: str` - Metric name
- `value: float` - Metric value
- `timestamp: datetime` - Recording time
- `meta_data: JSON` - Additional context

### UserSettings
Manages user preferences and configuration.

```python
from goldflipper.database.models import UserSettings

# Store a setting
setting = UserSettings(
    category="trading",
    key="max_position_size",
    value=5
)
```

Attributes:
- `id: UUID` - Unique identifier
- `category: str` - Setting category
- `key: str` - Setting name
- `value: JSON` - Setting value
- `last_modified: datetime` - Update timestamp

## Repositories

### PlayRepository
Manages play operations and queries.

```python
from goldflipper.database.repositories import PlayRepository

# Using the repository
with get_db_connection() as session:
    repo = PlayRepository(session)
    
    # Create play
    play = repo.create(play_data)
    
    # Query plays
    active_plays = repo.get_by_status(['new', 'open'])
    
    # Update play
    repo.update(play_id, {'status': 'closed'})
```

Methods:
- `create(data: Dict) -> Play`
- `get(play_id: UUID) -> Optional[Play]`
- `get_by_status(status: List[str]) -> List[Play]`
- `update(play_id: UUID, data: Dict) -> Play`
- Additional query methods

### TradeLogRepository
Manages trade execution records.

```python
from goldflipper.database.repositories import TradeLogRepository

# Using the repository
with get_db_connection() as session:
    repo = TradeLogRepository(session)
    
    # Log trade
    trade = repo.create(trade_data)
    
    # Get play trades
    trades = repo.get_by_play(play_id)
    
    # Calculate P/L
    pnl = repo.calculate_play_pnl(play_id)
```

Methods:
- `create(data: Dict) -> TradeLog`
- `get_by_play(play_id: UUID) -> List[TradeLog]`
- `calculate_play_pnl(play_id: UUID) -> float`
- Additional analytics methods

### AnalyticsRepository
Manages performance metrics and analytics.

```python
from goldflipper.database.repositories import AnalyticsRepository

# Using the repository
with get_db_connection() as session:
    repo = AnalyticsRepository(session)
    
    # Record metric
    metric = repo.record_metric(
        category="performance",
        metric="win_rate",
        value=0.65,
        meta_data={'timeframe': 'daily'}
    )
    
    # Get metrics
    metrics = repo.get_metrics_by_category('performance')
```

Methods:
- `record_metric(category: str, metric: str, value: float, meta_data: Dict = None)`
- `get_metrics_by_category(category: str) -> List[Analytics]`
- `get_latest_metric(category: str, metric: str) -> Optional[Analytics]`
- Additional analysis methods

## Connection Management

### get_db_connection
Context manager for database sessions.

```python
from goldflipper.database.connection import get_db_connection

with get_db_connection() as session:
    # Perform database operations
    plays = session.query(Play).all()
```

### init_db
Initialize database schema.

```python
from goldflipper.database.connection import init_db

# Create tables
init_db(force=False)  # Set force=True to recreate tables
```

## Error Handling
All database operations use SQLAlchemy's error handling:

```python
from sqlalchemy.exc import SQLAlchemyError

try:
    with get_db_connection() as session:
        repo = PlayRepository(session)
        play = repo.create(play_data)
except SQLAlchemyError as e:
    logger.error(f"Database error: {e}")
    raise
```

## Migration Tools
Tools for database schema updates:

```python
from goldflipper.database.migrations import upgrade, downgrade

# Apply migrations
upgrade()

# Rollback if needed
downgrade()
```

## Best Practices
1. Always use context managers for sessions
2. Implement proper error handling
3. Use repositories for data access
4. Keep transactions atomic
5. Validate data before persistence
6. Use appropriate indices for performance
7. Monitor query performance
8. Regular backups and maintenance 