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
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete, and_, or_, desc, func
from sqlalchemy.exc import SQLAlchemyError
import logging

from .models import Play, PlayStatusHistory, TradeLog, Analytics, MarketData, SystemState, UserSettings, TradingStrategy, ServiceBackup, LogEntry, ConfigTemplate, WatchdogEvent, ChartConfiguration, ToolState
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

class TradingStrategyRepository(BaseRepository):
    """
    Repository for managing TradingStrategy entities.
    
    This repository handles all database operations related to trading strategies,
    including versioning and validation.
    
    Attributes:
        model_class: Set to TradingStrategy model
    """
    
    def __init__(self, session: Session):
        super().__init__(session)
        self.model_class = TradingStrategy
    
    def get_active_strategies(self) -> List[TradingStrategy]:
        """
        Retrieve all active trading strategies.
        
        Returns:
            List[TradingStrategy]: List of active strategies
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            return self.session.query(TradingStrategy).filter(
                TradingStrategy.is_active == True
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving active strategies: {e}")
            raise
    
    def get_by_name(self, name: str) -> Optional[TradingStrategy]:
        """
        Retrieve a strategy by its name.
        
        Args:
            name (str): Strategy name to search for
            
        Returns:
            Optional[TradingStrategy]: Strategy if found, None otherwise
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            return self.session.query(TradingStrategy).filter(
                TradingStrategy.name == name
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving strategy by name: {e}")
            raise
    
    def deactivate_strategy(self, strategy_id: UUID) -> bool:
        """
        Deactivate a trading strategy.
        
        Args:
            strategy_id (UUID): Strategy ID to deactivate
            
        Returns:
            bool: True if strategy was deactivated, False if not found
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            strategy = self.get(strategy_id)
            if strategy:
                strategy.is_active = False
                self.session.flush()
                return True
            return False
        except SQLAlchemyError as e:
            logger.error(f"Error deactivating strategy: {e}")
            raise

class ServiceBackupRepository(BaseRepository):
    """
    Repository for managing ServiceBackup entities.
    
    This repository handles service state backups, including rotation and
    validation of backup data.
    
    Attributes:
        model_class: Set to ServiceBackup model
    """
    
    def __init__(self, session: Session):
        super().__init__(session)
        self.model_class = ServiceBackup
    
    def get_latest_backup(self, service_name: str) -> Optional[ServiceBackup]:
        """
        Get the most recent backup for a service.
        
        Args:
            service_name (str): Name of the service
            
        Returns:
            Optional[ServiceBackup]: Latest backup if found, None otherwise
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            return self.session.query(ServiceBackup).filter(
                ServiceBackup.service_name == service_name,
                ServiceBackup.is_valid == True
            ).order_by(
                ServiceBackup.created_at.desc()
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving latest backup: {e}")
            raise
    
    def get_backups_by_type(self, backup_type: str) -> List[ServiceBackup]:
        """
        Get all backups of a specific type.
        
        Args:
            backup_type (str): Type of backup to retrieve
            
        Returns:
            List[ServiceBackup]: List of matching backups
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            return self.session.query(ServiceBackup).filter(
                ServiceBackup.backup_type == backup_type
            ).order_by(
                ServiceBackup.created_at.desc()
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving backups by type: {e}")
            raise
    
    def cleanup_old_backups(self, service_name: str) -> int:
        """
        Remove backups that have exceeded their retention period.
        
        Args:
            service_name (str): Name of the service
            
        Returns:
            int: Number of backups removed
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            current_time = datetime.utcnow()
            query = self.session.query(ServiceBackup).filter(
                ServiceBackup.service_name == service_name,
                ServiceBackup.created_at <= current_time - func.make_interval(days=ServiceBackup.retention_days)
            )
            count = query.count()
            query.delete()
            self.session.flush()
            return count
        except SQLAlchemyError as e:
            logger.error(f"Error cleaning up old backups: {e}")
            raise
    
    def mark_invalid(self, backup_id: UUID, validation_errors: Dict[str, Any]) -> bool:
        """
        Mark a backup as invalid with validation errors.
        
        Args:
            backup_id (UUID): ID of the backup to mark
            validation_errors (Dict[str, Any]): Validation error details
            
        Returns:
            bool: True if backup was marked, False if not found
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            backup = self.get(backup_id)
            if backup:
                backup.is_valid = False
                backup.validation_errors = validation_errors
                self.session.flush()
                return True
            return False
        except SQLAlchemyError as e:
            logger.error(f"Error marking backup as invalid: {e}")
            raise

class LogEntryRepository(BaseRepository):
    """
    Repository for managing LogEntry entities.
    
    This repository handles structured logging operations, including
    log creation, querying, and analysis.
    
    Attributes:
        model_class: Set to LogEntry model
    """
    
    def __init__(self, session: Session):
        super().__init__(session)
        self.model_class = LogEntry
    
    def get_by_level(self, level: str) -> List[LogEntry]:
        """
        Get all logs of a specific level.
        
        Args:
            level (str): Log level to filter by
            
        Returns:
            List[LogEntry]: List of matching log entries
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            return self.session.query(LogEntry).filter(
                LogEntry.level == level
            ).order_by(LogEntry.timestamp.desc()).all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving logs by level: {e}")
            raise
    
    def get_by_component(
        self,
        component: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[LogEntry]:
        """
        Get logs for a specific component.
        
        Args:
            component (str): Component name
            start_time (datetime, optional): Start of time range
            end_time (datetime, optional): End of time range
            
        Returns:
            List[LogEntry]: List of matching log entries
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            query = self.session.query(LogEntry).filter(
                LogEntry.component == component
            )
            
            if start_time:
                query = query.filter(LogEntry.timestamp >= start_time)
            if end_time:
                query = query.filter(LogEntry.timestamp <= end_time)
                
            return query.order_by(LogEntry.timestamp.desc()).all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving logs for component: {e}")
            raise
    
    def get_by_trace_id(self, trace_id: str) -> List[LogEntry]:
        """
        Get all logs for a specific trace ID.
        
        Args:
            trace_id (str): Trace ID to search for
            
        Returns:
            List[LogEntry]: List of matching log entries
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            return self.session.query(LogEntry).filter(
                LogEntry.trace_id == trace_id
            ).order_by(LogEntry.timestamp).all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving logs by trace ID: {e}")
            raise
    
    def get_error_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[LogEntry]:
        """
        Get all error and critical logs.
        
        Args:
            start_time (datetime, optional): Start of time range
            end_time (datetime, optional): End of time range
            
        Returns:
            List[LogEntry]: List of error logs
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            query = self.session.query(LogEntry).filter(
                LogEntry.level.in_(['ERROR', 'CRITICAL'])
            )
            
            if start_time:
                query = query.filter(LogEntry.timestamp >= start_time)
            if end_time:
                query = query.filter(LogEntry.timestamp <= end_time)
                
            return query.order_by(LogEntry.timestamp.desc()).all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving error logs: {e}")
            raise
    
    def cleanup_old_logs(
        self,
        retention_days: int,
        exclude_levels: Optional[List[str]] = None
    ) -> int:
        """
        Remove logs older than retention period.
        
        Args:
            retention_days (int): Days to keep logs
            exclude_levels (List[str], optional): Log levels to preserve
            
        Returns:
            int: Number of logs removed
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            query = self.session.query(LogEntry).filter(
                LogEntry.timestamp < cutoff_date
            )
            
            if exclude_levels:
                query = query.filter(~LogEntry.level.in_(exclude_levels))
                
            count = query.count()
            query.delete(synchronize_session=False)
            self.session.flush()
            return count
        except SQLAlchemyError as e:
            logger.error(f"Error cleaning up old logs: {e}")
            raise

class ConfigTemplateRepository(BaseRepository):
    """
    Repository for managing ConfigTemplate entities.
    
    This repository handles configuration templates, including version tracking
    and schema validation.
    
    Attributes:
        model_class: Set to ConfigTemplate model
    """
    
    def __init__(self, session: Session):
        super().__init__(session)
        self.model_class = ConfigTemplate
    
    def get_by_name_version(
        self,
        name: str,
        version: str
    ) -> Optional[ConfigTemplate]:
        """
        Get a specific template version.
        
        Args:
            name (str): Template name
            version (str): Template version
            
        Returns:
            Optional[ConfigTemplate]: Template if found, None otherwise
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            return self.session.query(ConfigTemplate).filter(
                ConfigTemplate.name == name,
                ConfigTemplate.version == version
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving template {name} v{version}: {e}")
            raise
    
    def get_latest_version(self, name: str) -> Optional[ConfigTemplate]:
        """
        Get the latest version of a template.
        
        Args:
            name (str): Template name
            
        Returns:
            Optional[ConfigTemplate]: Latest template version if found
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            return self.session.query(ConfigTemplate).filter(
                ConfigTemplate.name == name,
                ConfigTemplate.is_active == True
            ).order_by(
                ConfigTemplate.created_at.desc()
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving latest version for {name}: {e}")
            raise
    
    def get_by_category(
        self,
        category: str,
        active_only: bool = True
    ) -> List[ConfigTemplate]:
        """
        Get all templates in a category.
        
        Args:
            category (str): Category to filter by
            active_only (bool): Whether to return only active templates
            
        Returns:
            List[ConfigTemplate]: List of matching templates
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            query = self.session.query(ConfigTemplate).filter(
                ConfigTemplate.category == category
            )
            
            if active_only:
                query = query.filter(ConfigTemplate.is_active == True)
                
            return query.order_by(
                ConfigTemplate.name,
                ConfigTemplate.version
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving templates for category {category}: {e}")
            raise
    
    def deactivate_template(
        self,
        name: str,
        version: str
    ) -> bool:
        """
        Deactivate a specific template version.
        
        Args:
            name (str): Template name
            version (str): Template version
            
        Returns:
            bool: True if template was deactivated, False if not found
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            template = self.get_by_name_version(name, version)
            if template:
                template.is_active = False
                self.session.flush()
                return True
            return False
        except SQLAlchemyError as e:
            logger.error(f"Error deactivating template {name} v{version}: {e}")
            raise
    
    def validate_config(
        self,
        name: str,
        config_data: Dict[str, Any],
        version: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validate configuration data against a template.
        
        Args:
            name (str): Template name
            config_data (Dict[str, Any]): Configuration to validate
            version (str, optional): Template version, uses latest if None
            
        Returns:
            Tuple[bool, Optional[Dict[str, Any]]]: (is_valid, validation_errors)
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            template = (
                self.get_by_name_version(name, version)
                if version
                else self.get_latest_version(name)
            )
            
            if not template:
                return False, {"error": "Template not found"}
            
            # TODO: Implement JSON Schema validation
            # For now, just check if all required fields exist
            required_fields = template.schema.get("required", [])
            missing_fields = [
                field for field in required_fields
                if field not in config_data
            ]
            
            if missing_fields:
                return False, {
                    "error": "Missing required fields",
                    "fields": missing_fields
                }
            
            return True, None
        except SQLAlchemyError as e:
            logger.error(f"Error validating config against {name}: {e}")
            raise

class WatchdogEventRepository(BaseRepository):
    """
    Repository for managing WatchdogEvent entities.
    
    This repository handles system monitoring events, including creation,
    resolution, and querying of events by various criteria.
    
    Attributes:
        model_class: Set to WatchdogEvent model
    """
    
    def __init__(self, session: Session):
        super().__init__(session)
        self.model_class = WatchdogEvent
    
    def get_unresolved_events(
        self,
        component: Optional[str] = None,
        severity: Optional[str] = None
    ) -> List[WatchdogEvent]:
        """
        Get unresolved events, optionally filtered by component and severity.
        
        Args:
            component (str, optional): Filter by component name
            severity (str, optional): Filter by severity level
            
        Returns:
            List[WatchdogEvent]: List of unresolved events
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            query = self.session.query(WatchdogEvent).filter(
                WatchdogEvent.resolved == False
            )
            
            if component:
                query = query.filter(WatchdogEvent.component == component)
            if severity:
                query = query.filter(WatchdogEvent.severity == severity)
                
            return query.order_by(WatchdogEvent.timestamp.desc()).all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving unresolved events: {e}")
            raise
    
    def resolve_event(
        self,
        event_id: UUID,
        resolution_notes: str,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> Optional[WatchdogEvent]:
        """
        Mark an event as resolved.
        
        Args:
            event_id (UUID): Event to resolve
            resolution_notes (str): Notes about the resolution
            meta_data (Dict[str, Any], optional): Additional resolution data
            
        Returns:
            Optional[WatchdogEvent]: Updated event if found
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            event = self.get(event_id)
            if event:
                event.resolved = True
                event.resolved_at = datetime.utcnow()
                event.resolution_notes = resolution_notes
                if meta_data:
                    event.meta_data = {
                        **(event.meta_data or {}),
                        'resolution': meta_data
                    }
                self.session.flush()
            return event
        except SQLAlchemyError as e:
            logger.error(f"Error resolving event {event_id}: {e}")
            raise
    
    def get_component_health(
        self,
        lookback_hours: int = 24
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get health status for all components.
        
        Args:
            lookback_hours (int): Hours of history to analyze
            
        Returns:
            Dict[str, Dict[str, Any]]: Component health metrics
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=lookback_hours)
            
            # Get all components with events in the period
            components = [r[0] for r in (
                self.session.query(WatchdogEvent.component)
                .filter(WatchdogEvent.timestamp >= cutoff_time)
                .distinct()
                .all()
            )]
            
            health_data = {}
            for component in components:
                # Get event counts by type and severity
                events = (
                    self.session.query(
                        WatchdogEvent.event_type,
                        WatchdogEvent.severity,
                        func.count().label('count')
                    )
                    .filter(
                        WatchdogEvent.component == component,
                        WatchdogEvent.timestamp >= cutoff_time
                    )
                    .group_by(WatchdogEvent.event_type, WatchdogEvent.severity)
                    .all()
                )
                
                # Get unresolved critical events
                unresolved_critical = (
                    self.session.query(func.count())
                    .filter(
                        WatchdogEvent.component == component,
                        WatchdogEvent.severity == 'critical',
                        WatchdogEvent.resolved == False
                    )
                    .scalar()
                )
                
                health_data[component] = {
                    'events_by_type': {},
                    'events_by_severity': {},
                    'unresolved_critical': unresolved_critical or 0
                }
                
                for event_type, severity, count in events:
                    if event_type not in health_data[component]['events_by_type']:
                        health_data[component]['events_by_type'][event_type] = 0
                    health_data[component]['events_by_type'][event_type] += count
                    
                    if severity not in health_data[component]['events_by_severity']:
                        health_data[component]['events_by_severity'][severity] = 0
                    health_data[component]['events_by_severity'][severity] += count
            
            return health_data
        except SQLAlchemyError as e:
            logger.error("Error getting component health data: {e}")
            raise
    
    def cleanup_old_events(
        self,
        retention_days: int,
        exclude_unresolved: bool = True
    ) -> int:
        """
        Remove old events that have exceeded retention period.
        
        Args:
            retention_days (int): Days to keep events
            exclude_unresolved (bool): Whether to keep unresolved events
            
        Returns:
            int: Number of events removed
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            query = self.session.query(WatchdogEvent).filter(
                WatchdogEvent.timestamp < cutoff_date
            )
            
            if exclude_unresolved:
                query = query.filter(WatchdogEvent.resolved == True)
                
            count = query.count()
            query.delete(synchronize_session=False)
            self.session.flush()
            return count
        except SQLAlchemyError as e:
            logger.error(f"Error cleaning up old events: {e}")
            raise

class ChartConfigurationRepository(BaseRepository):
    """
    Repository for managing ChartConfiguration entities.
    
    This repository handles chart configurations, including default settings,
    user preferences, and indicator management.
    
    Attributes:
        model_class: Set to ChartConfiguration model
    """
    
    def __init__(self, session: Session):
        super().__init__(session)
        self.model_class = ChartConfiguration
    
    def get_by_name(self, name: str) -> Optional[ChartConfiguration]:
        """
        Get a configuration by name.
        
        Args:
            name (str): Configuration name
            
        Returns:
            Optional[ChartConfiguration]: Configuration if found
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            return self.session.query(ChartConfiguration).filter(
                ChartConfiguration.name == name
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving chart configuration {name}: {e}")
            raise
    
    def get_default_config(
        self,
        chart_type: Optional[str] = None
    ) -> Optional[ChartConfiguration]:
        """
        Get default configuration, optionally for a specific chart type.
        
        Args:
            chart_type (str, optional): Type of chart
            
        Returns:
            Optional[ChartConfiguration]: Default configuration if found
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            query = self.session.query(ChartConfiguration).filter(
                ChartConfiguration.is_default == True
            )
            
            if chart_type:
                query = query.filter(ChartConfiguration.chart_type == chart_type)
                
            return query.first()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving default configuration: {e}")
            raise
    
    def set_as_default(
        self,
        config_id: UUID,
        chart_type: Optional[str] = None
    ) -> bool:
        """
        Set a configuration as default.
        
        Args:
            config_id (UUID): Configuration to set as default
            chart_type (str, optional): Only set as default for this type
            
        Returns:
            bool: True if configuration was set as default
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            # Clear existing defaults
            query = self.session.query(ChartConfiguration).filter(
                ChartConfiguration.is_default == True
            )
            
            if chart_type:
                query = query.filter(ChartConfiguration.chart_type == chart_type)
                
            query.update({'is_default': False})
            
            # Set new default
            config = self.get(config_id)
            if config:
                config.is_default = True
                self.session.flush()
                return True
            return False
        except SQLAlchemyError as e:
            logger.error(f"Error setting default configuration: {e}")
            raise
    
    def get_by_timeframe(
        self,
        timeframe: str,
        chart_type: Optional[str] = None
    ) -> List[ChartConfiguration]:
        """
        Get configurations for a specific timeframe.
        
        Args:
            timeframe (str): Timeframe to filter by
            chart_type (str, optional): Type of chart
            
        Returns:
            List[ChartConfiguration]: List of matching configurations
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            query = self.session.query(ChartConfiguration).filter(
                ChartConfiguration.timeframe == timeframe
            )
            
            if chart_type:
                query = query.filter(ChartConfiguration.chart_type == chart_type)
                
            return query.all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving configurations for timeframe {timeframe}: {e}")
            raise
    
    def clone_configuration(
        self,
        config_id: UUID,
        new_name: str,
        modifications: Optional[Dict[str, Any]] = None
    ) -> Optional[ChartConfiguration]:
        """
        Clone an existing configuration with optional modifications.
        
        Args:
            config_id (UUID): Configuration to clone
            new_name (str): Name for the new configuration
            modifications (Dict[str, Any], optional): Changes to apply
            
        Returns:
            Optional[ChartConfiguration]: New configuration if successful
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            source = self.get(config_id)
            if not source:
                return None
                
            data = source.to_dict()
            data.pop('id', None)  # Remove ID to create new
            data['name'] = new_name
            data['is_default'] = False
            data['created_at'] = datetime.utcnow()
            
            if modifications:
                # Update specific fields
                for key, value in modifications.items():
                    if key in data:
                        if isinstance(data[key], dict) and isinstance(value, dict):
                            data[key].update(value)
                        else:
                            data[key] = value
            
            return self.create(data)
        except SQLAlchemyError as e:
            logger.error(f"Error cloning configuration: {e}")
            raise

class ToolStateRepository(BaseRepository):
    """
    Repository for managing ToolState entities.
    
    This repository handles tool state persistence, configuration management,
    and state recovery operations.
    
    Attributes:
        model_class: Set to ToolState model
    """
    
    def __init__(self, session: Session):
        super().__init__(session)
        self.model_class = ToolState
    
    def get_by_name(
        self,
        tool_name: str,
        version: Optional[str] = None
    ) -> Optional[ToolState]:
        """
        Get state for a specific tool.
        
        Args:
            tool_name (str): Name of the tool
            version (str, optional): Tool version
            
        Returns:
            Optional[ToolState]: Tool state if found
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            query = self.session.query(ToolState).filter(
                ToolState.tool_name == tool_name
            )
            
            if version:
                query = query.filter(ToolState.version == version)
                
            return query.first()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving state for {tool_name}: {e}")
            raise
    
    def get_enabled_tools(self) -> List[ToolState]:
        """
        Get states for all enabled tools.
        
        Returns:
            List[ToolState]: List of enabled tool states
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            return self.session.query(ToolState).filter(
                ToolState.is_enabled == True
            ).all()
        except SQLAlchemyError as e:
            logger.error("Error retrieving enabled tools: {e}")
            raise
    
    def update_state(
        self,
        tool_name: str,
        state: Dict[str, Any],
        error_state: Optional[Dict[str, Any]] = None
    ) -> Optional[ToolState]:
        """
        Update a tool's state.
        
        Args:
            tool_name (str): Name of the tool
            state (Dict[str, Any]): New state data
            error_state (Dict[str, Any], optional): Error information
            
        Returns:
            Optional[ToolState]: Updated tool state if found
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            tool_state = self.get_by_name(tool_name)
            if tool_state:
                tool_state.state = state
                tool_state.last_active = datetime.utcnow()
                if error_state is not None:
                    tool_state.error_state = error_state
                self.session.flush()
            return tool_state
        except SQLAlchemyError as e:
            logger.error(f"Error updating state for {tool_name}: {e}")
            raise
    
    def update_config(
        self,
        tool_name: str,
        config: Dict[str, Any]
    ) -> Optional[ToolState]:
        """
        Update a tool's configuration.
        
        Args:
            tool_name (str): Name of the tool
            config (Dict[str, Any]): New configuration
            
        Returns:
            Optional[ToolState]: Updated tool state if found
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            tool_state = self.get_by_name(tool_name)
            if tool_state:
                tool_state.config = config
                self.session.flush()
            return tool_state
        except SQLAlchemyError as e:
            logger.error(f"Error updating config for {tool_name}: {e}")
            raise
    
    def set_enabled(
        self,
        tool_name: str,
        enabled: bool
    ) -> bool:
        """
        Enable or disable a tool.
        
        Args:
            tool_name (str): Name of the tool
            enabled (bool): Whether to enable the tool
            
        Returns:
            bool: True if tool state was updated
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            tool_state = self.get_by_name(tool_name)
            if tool_state:
                tool_state.is_enabled = enabled
                self.session.flush()
                return True
            return False
        except SQLAlchemyError as e:
            logger.error(f"Error setting enabled state for {tool_name}: {e}")
            raise
    
    def get_inactive_tools(
        self,
        inactive_minutes: int
    ) -> List[ToolState]:
        """
        Get tools that haven't been active recently.
        
        Args:
            inactive_minutes (int): Minutes of inactivity threshold
            
        Returns:
            List[ToolState]: List of inactive tool states
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=inactive_minutes)
            return self.session.query(ToolState).filter(
                ToolState.is_enabled == True,
                ToolState.last_active < cutoff_time
            ).all()
        except SQLAlchemyError as e:
            logger.error("Error retrieving inactive tools: {e}")
            raise 