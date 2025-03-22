"""
Database Repositories for GoldFlipper
=================================

This module implements the Repository pattern for database operations in the
GoldFlipper trading system. Each repository class provides a high-level interface
for performing CRUD operations on specific database entities.

Repository Pattern
---------------
The Repository pattern abstracts the data persistence layer, providing a more
object-oriented view of the persistence layer. This implementation:

- Centralizes common data access functionality
- Provides consistent interface across different entity types
- Implements proper transaction management
- Handles database errors gracefully
- Maintains separation of concerns

Available Repositories
-------------------
1. PlayRepository
   - Manages options trading plays
   - Handles play status transitions
   - Maintains play relationships

2. PlayStatusHistoryRepository
   - Records play status changes
   - Manages order state tracking
   - Provides audit trail functionality

3. TradeLogRepository
   - Records trade executions
   - Calculates and stores P/L
   - Manages trade metrics

Usage Example
-----------
```python
from goldflipper.database.repositories import PlayRepository
from goldflipper.database.connection import get_db_connection

# Create a new play
with get_db_connection() as session:
    repo = PlayRepository(session)
    play = repo.create(play_data)
    
# Query plays
active_plays = repo.get_by_status('open')
```
"""

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete, and_, or_, desc, func
from sqlalchemy.exc import SQLAlchemyError
import logging

from .models import Play, PlayStatusHistory, TradeLog, Analytics, MarketData, SystemState, UserSettings
from .connection import get_db_connection

logger = logging.getLogger(__name__)

class BaseRepository:
    """
    Base repository class implementing common database operations.
    
    This class provides the foundation for specific entity repositories,
    implementing common CRUD operations and error handling.
    
    Args:
        session (Session): SQLAlchemy session for database operations
        
    Attributes:
        session (Session): Active database session
        model_class: SQLAlchemy model class this repository handles
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.model_class = None  # Set by child classes
    
    def get(self, id: UUID) -> Optional[Any]:
        """
        Retrieve an entity by its ID.
        
        Args:
            id (UUID): Entity's unique identifier
            
        Returns:
            Optional[Any]: Entity instance if found, None otherwise
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            return self.session.query(self.model_class).get(id)
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving {self.model_class.__name__}: {e}")
            raise
    
    def get_all(self) -> List[Any]:
        """
        Retrieve all entities of this type.
        
        Returns:
            List[Any]: List of all entities
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            return self.session.query(self.model_class).all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving all {self.model_class.__name__}s: {e}")
            raise
    
    def create(self, data: Dict[str, Any]) -> Any:
        """
        Create a new entity.
        
        Args:
            data (Dict[str, Any]): Entity data
            
        Returns:
            Any: Created entity instance
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            instance = self.model_class.from_dict(data)
            self.session.add(instance)
            self.session.flush()
            return instance
        except SQLAlchemyError as e:
            logger.error(f"Error creating {self.model_class.__name__}: {e}")
            raise
    
    def update(self, id: UUID, data: Dict[str, Any]) -> Optional[Any]:
        """
        Update an existing entity.
        
        Args:
            id (UUID): Entity's unique identifier
            data (Dict[str, Any]): Updated entity data
            
        Returns:
            Optional[Any]: Updated entity instance if found
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            instance = self.get(id)
            if instance:
                for key, value in data.items():
                    setattr(instance, key, value)
                self.session.flush()
            return instance
        except SQLAlchemyError as e:
            logger.error(f"Error updating {self.model_class.__name__}: {e}")
            raise
    
    def delete(self, id: UUID) -> bool:
        """
        Delete an entity.
        
        Args:
            id (UUID): Entity's unique identifier
            
        Returns:
            bool: True if entity was deleted, False if not found
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            instance = self.get(id)
            if instance:
                self.session.delete(instance)
                self.session.flush()
                return True
            return False
        except SQLAlchemyError as e:
            logger.error(f"Error deleting {self.model_class.__name__}: {e}")
            raise

class PlayRepository(BaseRepository):
    """
    Repository for managing Play entities.
    
    This repository handles all database operations related to options trading
    plays, including status management and relationship handling.
    
    Attributes:
        model_class: Set to Play model
    """
    
    def __init__(self, session: Session):
        super().__init__(session)
        self.model_class = Play
    
    def get_by_status(self, status: str) -> List[Play]:
        """
        Retrieve plays by their current status.
        
        Args:
            status (str): Status to filter by ('new', 'open', 'closed', 'expired')
            
        Returns:
            List[Play]: List of plays with the specified status
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            return self.session.query(Play).filter(Play.status == status).all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving plays by status: {e}")
            raise
    
    def get_by_symbol(self, symbol: str) -> List[Play]:
        """Get all plays for a specific symbol."""
        with get_db_connection() as conn:
            result = conn.execute(
                select(Play).where(Play.symbol == symbol)
            ).all()
            return [row[0] for row in result]
    
    def get_active_plays(self) -> List[Play]:
        """
        Retrieve all active (new or open) plays.
        
        Returns:
            List[Play]: List of active plays
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            return self.session.query(Play).filter(
                Play.status.in_(['new', 'open'])
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving active plays: {e}")
            raise
    
    def update_status(self, play_id: UUID, new_status: str) -> Optional[Play]:
        """
        Update a play's status and create a status history entry.
        
        Args:
            play_id (UUID): Play's unique identifier
            new_status (str): New status value
            
        Returns:
            Optional[Play]: Updated play instance if found
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            play = self.get(play_id)
            if play:
                play.status = new_status
                play.last_modified = datetime.utcnow()
                
                # Create status history entry
                history = PlayStatusHistory(
                    play_id=play_id,
                    status=new_status,
                    timestamp=datetime.utcnow()
                )
                self.session.add(history)
                self.session.flush()
                
            return play
        except SQLAlchemyError as e:
            logger.error(f"Error updating play status: {e}")
            raise

class PlayStatusHistoryRepository(BaseRepository):
    """
    Repository for managing PlayStatusHistory entities.
    
    This repository handles the tracking and querying of play status changes
    and order states.
    
    Attributes:
        model_class: Set to PlayStatusHistory model
    """
    
    def __init__(self, session: Session):
        super().__init__(session)
        self.model_class = PlayStatusHistory
    
    def get_by_play(self, play_id: UUID) -> List[PlayStatusHistory]:
        """
        Retrieve all status history entries for a play.
        
        Args:
            play_id (UUID): Play's unique identifier
            
        Returns:
            List[PlayStatusHistory]: List of status history entries
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            return self.session.query(PlayStatusHistory).filter(
                PlayStatusHistory.play_id == play_id
            ).order_by(PlayStatusHistory.timestamp.desc()).all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving status history: {e}")
            raise
    
    def get_latest_status(self, play_id: UUID) -> Optional[PlayStatusHistory]:
        """
        Get the most recent status history entry for a play.
        
        Args:
            play_id (UUID): Play's unique identifier
            
        Returns:
            Optional[PlayStatusHistory]: Latest status entry if found
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            return self.session.query(PlayStatusHistory).filter(
                PlayStatusHistory.play_id == play_id
            ).order_by(PlayStatusHistory.timestamp.desc()).first()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving latest status: {e}")
            raise

class TradeLogRepository(BaseRepository):
    """
    Repository for managing TradeLog entities.
    
    This repository handles the recording and querying of trade executions
    and their associated metrics.
    
    Attributes:
        model_class: Set to TradeLog model
    """
    
    def __init__(self, session: Session):
        super().__init__(session)
        self.model_class = TradeLog
    
    def get_by_play(self, play_id: UUID) -> List[TradeLog]:
        """
        Retrieve all trade logs for a play.
        
        Args:
            play_id (UUID): Play's unique identifier
            
        Returns:
            List[TradeLog]: List of trade logs
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            return self.session.query(TradeLog).filter(
                TradeLog.play_id == play_id
            ).order_by(TradeLog.datetime_open.desc()).all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving trade logs: {e}")
            raise
    
    def get_profitable_trades(self) -> List[TradeLog]:
        """
        Retrieve all profitable trades.
        
        Returns:
            List[TradeLog]: List of trades with positive P/L
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            return self.session.query(TradeLog).filter(
                TradeLog.profit_loss > 0
            ).order_by(TradeLog.profit_loss.desc()).all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving profitable trades: {e}")
            raise
    
    def calculate_total_pnl(self) -> float:
        """
        Calculate total profit/loss across all closed trades.
        
        Returns:
            float: Total P/L in dollars
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            result = self.session.query(
                func.sum(TradeLog.profit_loss)
            ).scalar()
            return float(result) if result is not None else 0.0
        except SQLAlchemyError as e:
            logger.error(f"Error calculating total P/L: {e}")
            raise

    def get_profit_loss_summary(
        self, 
        start_date: Optional[datetime] = None, 
        end_date: Optional[datetime] = None
    ) -> Dict[str, float]:
        """Get profit/loss summary for all trades or within a date range."""
        query = select(
            func.count().label('total_trades'),
            func.sum(TradeLog.profit_loss).label('total_pl'),
            func.avg(TradeLog.profit_loss_pct).label('avg_pl_pct')
        )
        
        if start_date and end_date:
            query = query.where(
                TradeLog.datetime_open >= start_date,
                TradeLog.datetime_open <= end_date
            )
        
        with get_db_connection() as conn:
            result = conn.execute(query).first()
            
            return {
                'total_trades': result.total_trades or 0,
                'total_pl': float(result.total_pl or 0),
                'avg_pl_pct': float(result.avg_pl_pct or 0)
            }

class MarketDataRepository:
    """
    Repository for market data operations.
    
    This repository handles storage and retrieval of market data,
    including OHLCV data and options metrics.
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_latest_price(self, symbol: str) -> Optional[MarketData]:
        """Get the most recent price data for a symbol."""
        try:
            return (self.session.query(MarketData)
                   .filter(MarketData.symbol == symbol)
                   .order_by(desc(MarketData.timestamp))
                   .first())
        except SQLAlchemyError as e:
            logger.error(f"Error getting latest price for {symbol}: {e}")
            raise
    
    def get_price_history(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[MarketData]:
        """Get historical price data for a symbol."""
        try:
            return (self.session.query(MarketData)
                   .filter(and_(
                       MarketData.symbol == symbol,
                       MarketData.timestamp >= start_time,
                       MarketData.timestamp <= end_time
                   ))
                   .order_by(MarketData.timestamp)
                   .all())
        except SQLAlchemyError as e:
            logger.error(f"Error getting price history for {symbol}: {e}")
            raise
    
    def get_option_metrics(self, symbol: str) -> Optional[MarketData]:
        """Get latest option metrics for a symbol."""
        try:
            return (self.session.query(MarketData)
                   .filter(and_(
                       MarketData.symbol == symbol,
                       MarketData.implied_volatility.isnot(None)
                   ))
                   .order_by(desc(MarketData.timestamp))
                   .first())
        except SQLAlchemyError as e:
            logger.error(f"Error getting option metrics for {symbol}: {e}")
            raise
    
    def bulk_insert(self, data_points: List[Dict[str, Any]]) -> None:
        """Bulk insert market data points."""
        try:
            self.session.bulk_insert_mappings(
                MarketData,
                data_points
            )
        except SQLAlchemyError as e:
            logger.error(f"Error bulk inserting market data: {e}")
            raise

class UserSettingsRepository:
    """
    Repository for user settings operations.
    
    This repository manages user preferences and configuration data.
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_setting(
        self,
        category: str,
        key: str
    ) -> Optional[UserSettings]:
        """Get a specific setting."""
        try:
            return (self.session.query(UserSettings)
                   .filter(and_(
                       UserSettings.category == category,
                       UserSettings.key == key
                   ))
                   .first())
        except SQLAlchemyError as e:
            logger.error(f"Error getting setting {category}.{key}: {e}")
            raise
    
    def get_category_settings(
        self,
        category: str
    ) -> List[UserSettings]:
        """Get all settings in a category."""
        try:
            return (self.session.query(UserSettings)
                   .filter(UserSettings.category == category)
                   .all())
        except SQLAlchemyError as e:
            logger.error(f"Error getting settings for category {category}: {e}")
            raise
    
    def set_setting(
        self,
        category: str,
        key: str,
        value: Any
    ) -> UserSettings:
        """Set a setting value."""
        try:
            setting = self.get_setting(category, key)
            if setting:
                setting.value = value
                setting.last_modified = datetime.utcnow()
            else:
                setting = UserSettings(
                    category=category,
                    key=key,
                    value=value
                )
                self.session.add(setting)
            return setting
        except SQLAlchemyError as e:
            logger.error(f"Error setting {category}.{key}: {e}")
            raise

class SystemStateRepository:
    """
    Repository for system state operations.
    
    This repository manages system component states and recovery data.
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_component_state(
        self,
        component: str
    ) -> Optional[SystemState]:
        """Get the current state of a component."""
        try:
            return (self.session.query(SystemState)
                   .filter(and_(
                       SystemState.component == component,
                       SystemState.is_active == True
                   ))
                   .order_by(desc(SystemState.timestamp))
                   .first())
        except SQLAlchemyError as e:
            logger.error(f"Error getting state for {component}: {e}")
            raise
    
    def update_component_state(
        self,
        component: str,
        state: Dict[str, Any],
        is_active: bool = True
    ) -> SystemState:
        """Update a component's state."""
        try:
            # Deactivate old states
            (self.session.query(SystemState)
             .filter(and_(
                 SystemState.component == component,
                 SystemState.is_active == True
             ))
             .update({'is_active': False}))
            
            # Create new state
            new_state = SystemState(
                component=component,
                state=state,
                is_active=is_active
            )
            self.session.add(new_state)
            return new_state
        except SQLAlchemyError as e:
            logger.error(f"Error updating state for {component}: {e}")
            raise
    
    def get_active_components(self) -> List[str]:
        """Get list of active components."""
        try:
            return [r[0] for r in (
                self.session.query(SystemState.component)
                .filter(SystemState.is_active == True)
                .distinct()
                .all()
            )]
        except SQLAlchemyError as e:
            logger.error("Error getting active components: {e}")
            raise

class AnalyticsRepository:
    """
    Repository for analytics operations.
    
    This repository manages trading analytics and performance metrics.
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def record_metric(
        self,
        category: str,
        metric: str,
        value: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Analytics:
        """Record a new metric value."""
        try:
            analytics = Analytics(
                category=category,
                metric=metric,
                value=value,
                metadata=metadata or {}
            )
            self.session.add(analytics)
            return analytics
        except SQLAlchemyError as e:
            logger.error(f"Error recording metric {category}.{metric}: {e}")
            raise
    
    def get_metric_history(
        self,
        category: str,
        metric: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Analytics]:
        """Get historical values for a metric."""
        try:
            query = (self.session.query(Analytics)
                    .filter(and_(
                        Analytics.category == category,
                        Analytics.metric == metric
                    )))
            
            if start_time:
                query = query.filter(Analytics.timestamp >= start_time)
            if end_time:
                query = query.filter(Analytics.timestamp <= end_time)
            
            return query.order_by(Analytics.timestamp).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting history for {category}.{metric}: {e}")
            raise
    
    def get_latest_metrics(
        self,
        category: str
    ) -> List[Tuple[str, float]]:
        """Get latest values for all metrics in a category."""
        try:
            subq = (self.session.query(
                Analytics.metric,
                func.max(Analytics.timestamp).label('max_ts')
            )
            .filter(Analytics.category == category)
            .group_by(Analytics.metric)
            .subquery())
            
            return (self.session.query(
                Analytics.metric,
                Analytics.value
            )
            .join(subq, and_(
                Analytics.metric == subq.c.metric,
                Analytics.timestamp == subq.c.max_ts
            ))
            .all())
        except SQLAlchemyError as e:
            logger.error(f"Error getting latest metrics for {category}: {e}")
            raise 