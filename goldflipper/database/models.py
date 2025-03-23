"""
SQLAlchemy Models for GoldFlipper Database
=======================================

This module defines the SQLAlchemy ORM models that represent the database tables
in the GoldFlipper trading system. These models provide a Pythonic interface to
the database and handle data validation, relationships, and type conversions.

Model Structure
-------------
1. Play
   - Represents an options trading play
   - Contains core trading parameters
   - Manages relationships with history and logs

2. PlayStatusHistory
   - Tracks status changes of plays
   - Records order IDs and states
   - Maintains audit trail

3. TradeLog
   - Records trade execution details
   - Tracks profit/loss
   - Stores Greeks at entry

4. TradingStrategy
   - Represents a trading strategy configuration
   - Contains strategy parameters and metadata
   - Tracks strategy versions and usage

Implementation Details
-------------------
The models use SQLAlchemy's declarative base system and include:
- Type validation
- Relationship management
- JSON field handling
- Automatic timestamp management
- UUID primary keys
"""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, 
    Boolean, ForeignKey, JSON, CheckConstraint, Index, UniqueConstraint, Text
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID as SQLUUID
from sqlalchemy.types import TypeDecorator

Base = declarative_base()

class SQLUUID(TypeDecorator):
    """UUID type for SQLAlchemy that works with DuckDB."""
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return UUID(value)

class Play(Base):
    """
    Model representing an options trading play.
    
    This is the core model of the system, representing an options trading play
    from creation through execution and closure.
    
    Attributes:
        play_id (UUID): Unique identifier for the play
        play_name (str): Human-readable name for the play
        symbol (str): Trading symbol (e.g., 'SPY')
        trade_type (str): Type of trade ('CALL' or 'PUT')
        strike_price (float): Option strike price
        expiration_date (datetime): Option expiration date
        contracts (int): Number of contracts
        status (str): Current status ('new', 'open', 'closed', 'expired')
        play_class (str): Class of play ('SIMPLE', 'OCO', 'OTO')
        creation_date (datetime): When the play was created
        option_contract_symbol (str): Full option contract symbol
        entry_point (dict): Entry conditions and parameters
        take_profit (dict): Take profit parameters
        stop_loss (dict): Stop loss parameters
        strategy_id (UUID): Reference to the trading strategy
        creator (str): Who/what created the play
        last_modified (datetime): Last modification timestamp
        
    Relationships:
        status_history: List of status changes
        trade_logs: List of trade executions
        trading_strategy: Associated trading strategy
    """
    
    __tablename__ = 'plays'
    
    play_id = Column(SQLUUID, primary_key=True, default=uuid4)
    play_name = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    trade_type = Column(String, nullable=False)
    strike_price = Column(Float, nullable=False)
    expiration_date = Column(DateTime, nullable=False)
    contracts = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    play_class = Column(String, nullable=False)
    creation_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    option_contract_symbol = Column(String)
    entry_point = Column(JSON)
    take_profit = Column(JSON)
    stop_loss = Column(JSON)
    strategy_id = Column(SQLUUID, ForeignKey('trading_strategies.strategy_id'))
    creator = Column(String)
    last_modified = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    status_history = relationship("PlayStatusHistory", back_populates="play")
    trade_logs = relationship("TradeLog", back_populates="play")
    trading_strategy = relationship("TradingStrategy", back_populates="plays")
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            status.in_(['new', 'open', 'closed', 'expired']),
            name='valid_status'
        ),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the model to a dictionary.
        
        This method provides a serializable representation of the play,
        suitable for JSON encoding or API responses.
        
        Returns:
            dict: Dictionary representation of the play
        """
        return {
            'play_id': str(self.play_id),
            'play_name': self.play_name,
            'symbol': self.symbol,
            'trade_type': self.trade_type,
            'strike_price': float(self.strike_price),
            'expiration_date': self.expiration_date.isoformat(),
            'contracts': self.contracts,
            'status': self.status,
            'play_class': self.play_class,
            'creation_date': self.creation_date.isoformat(),
            'option_contract_symbol': self.option_contract_symbol,
            'entry_point': self.entry_point,
            'take_profit': self.take_profit,
            'stop_loss': self.stop_loss,
            'strategy_id': str(self.strategy_id) if self.strategy_id else None,
            'creator': self.creator,
            'last_modified': self.last_modified.isoformat() if self.last_modified else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Play':
        """
        Create a model instance from a dictionary.
        
        This method handles the conversion of string dates to datetime objects
        and ensures proper type conversion for all fields.
        
        Args:
            data (dict): Dictionary containing play data
            
        Returns:
            Play: New Play instance
        """
        if 'play_id' in data:
            data['play_id'] = UUID(data['play_id'])
        if 'expiration_date' in data:
            data['expiration_date'] = datetime.fromisoformat(data['expiration_date'])
        if 'creation_date' in data:
            data['creation_date'] = datetime.fromisoformat(data['creation_date'])
        if 'last_modified' in data and data['last_modified']:
            data['last_modified'] = datetime.fromisoformat(data['last_modified'])
        return cls(**data)

class PlayStatusHistory(Base):
    """
    Model representing play status history.
    
    This model tracks all status changes and order states for a play,
    providing a complete audit trail of the play's lifecycle.
    
    Attributes:
        history_id (UUID): Unique identifier for the history entry
        play_id (UUID): Reference to the parent play
        status (str): Status at this point
        order_id (str): Associated order ID
        order_status (str): Status of the order
        position_exists (bool): Whether position exists
        timestamp (datetime): When this status was recorded
        closing_order_id (str): ID of closing order
        closing_order_status (str): Status of closing order
        contingency_order_id (str): ID of contingency order
        contingency_order_status (str): Status of contingency order
        conditionals_handled (bool): Whether conditionals were processed
    """
    
    __tablename__ = 'play_status_history'
    
    history_id = Column(SQLUUID, primary_key=True, default=uuid4)
    play_id = Column(SQLUUID, ForeignKey('plays.play_id'), nullable=False)
    status = Column(String, nullable=False)
    order_id = Column(String)
    order_status = Column(String)
    position_exists = Column(Boolean)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    closing_order_id = Column(String)
    closing_order_status = Column(String)
    contingency_order_id = Column(String)
    contingency_order_status = Column(String)
    conditionals_handled = Column(Boolean, default=False)
    
    # Relationships
    play = relationship("Play", back_populates="status_history")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the model to a dictionary.
        
        Returns:
            dict: Dictionary representation of the status history
        """
        return {
            'history_id': str(self.history_id),
            'play_id': str(self.play_id),
            'status': self.status,
            'order_id': self.order_id,
            'order_status': self.order_status,
            'position_exists': self.position_exists,
            'timestamp': self.timestamp.isoformat(),
            'closing_order_id': self.closing_order_id,
            'closing_order_status': self.closing_order_status,
            'contingency_order_id': self.contingency_order_id,
            'contingency_order_status': self.contingency_order_status,
            'conditionals_handled': self.conditionals_handled
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlayStatusHistory':
        """
        Create a model instance from a dictionary.
        
        Args:
            data (dict): Dictionary containing status history data
            
        Returns:
            PlayStatusHistory: New PlayStatusHistory instance
        """
        if 'history_id' in data:
            data['history_id'] = UUID(data['history_id'])
        if 'play_id' in data:
            data['play_id'] = UUID(data['play_id'])
        if 'timestamp' in data:
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

class TradeLog(Base):
    """
    Model representing trade execution logs.
    
    This model records the details of trade executions, including entry and exit
    prices, premiums, and calculated profit/loss.
    
    Attributes:
        trade_id (UUID): Unique identifier for the trade
        play_id (UUID): Reference to the parent play
        datetime_open (datetime): When the trade was opened
        datetime_close (datetime): When the trade was closed
        price_open (float): Stock price at entry
        price_close (float): Stock price at exit
        premium_open (float): Option premium at entry
        premium_close (float): Option premium at exit
        delta_open (float): Delta at entry
        theta_open (float): Theta at entry
        close_type (str): How the trade was closed
        close_condition (str): What triggered the close
        profit_loss (float): Absolute P/L in dollars
        profit_loss_pct (float): Percentage P/L
    """
    
    __tablename__ = 'trade_logs'
    
    trade_id = Column(SQLUUID, primary_key=True, default=uuid4)
    play_id = Column(SQLUUID, ForeignKey('plays.play_id'), nullable=False)
    datetime_open = Column(DateTime)
    datetime_close = Column(DateTime)
    price_open = Column(Float)
    price_close = Column(Float)
    premium_open = Column(Float)
    premium_close = Column(Float)
    delta_open = Column(Float)
    theta_open = Column(Float)
    close_type = Column(String)
    close_condition = Column(String)
    profit_loss = Column(Float)
    profit_loss_pct = Column(Float)
    
    # Relationships
    play = relationship("Play", back_populates="trade_logs")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the model to a dictionary.
        
        Returns:
            dict: Dictionary representation of the trade log
        """
        return {
            'trade_id': str(self.trade_id),
            'play_id': str(self.play_id),
            'datetime_open': self.datetime_open.isoformat() if self.datetime_open else None,
            'datetime_close': self.datetime_close.isoformat() if self.datetime_close else None,
            'price_open': float(self.price_open) if self.price_open is not None else None,
            'price_close': float(self.price_close) if self.price_close is not None else None,
            'premium_open': float(self.premium_open) if self.premium_open is not None else None,
            'premium_close': float(self.premium_close) if self.premium_close is not None else None,
            'delta_open': float(self.delta_open) if self.delta_open is not None else None,
            'theta_open': float(self.theta_open) if self.theta_open is not None else None,
            'close_type': self.close_type,
            'close_condition': self.close_condition,
            'profit_loss': float(self.profit_loss) if self.profit_loss is not None else None,
            'profit_loss_pct': float(self.profit_loss_pct) if self.profit_loss_pct is not None else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradeLog':
        """
        Create a model instance from a dictionary.
        
        Args:
            data (dict): Dictionary containing trade log data
            
        Returns:
            TradeLog: New TradeLog instance
        """
        if 'trade_id' in data:
            data['trade_id'] = UUID(data['trade_id'])
        if 'play_id' in data:
            data['play_id'] = UUID(data['play_id'])
        if 'datetime_open' in data and data['datetime_open']:
            data['datetime_open'] = datetime.fromisoformat(data['datetime_open'])
        if 'datetime_close' in data and data['datetime_close']:
            data['datetime_close'] = datetime.fromisoformat(data['datetime_close'])
        return cls(**data)

class MarketData(Base):
    """
    Historical and real-time market data.
    
    This model stores both historical and real-time market data for various
    financial instruments, including stocks and options. It includes OHLCV data
    as well as options-specific metrics like Greeks and implied volatility.
    
    Attributes:
        id (UUID): Unique identifier
        symbol (str): Trading symbol
        timestamp (datetime): Data timestamp
        open (float): Opening price
        high (float): High price
        low (float): Low price
        close (float): Closing price
        volume (int): Trading volume
        source (str): Data provider name
        implied_volatility (float): Option implied volatility
        open_interest (int): Option open interest
        delta (float): Option delta
        gamma (float): Option gamma
        theta (float): Option theta
        vega (float): Option vega
    """
    __tablename__ = 'market_data'
    
    id = Column(SQLUUID, primary_key=True, default=uuid4)
    symbol = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Integer)
    source = Column(String)  # Data provider
    
    # Options-specific data
    implied_volatility = Column(Float)
    open_interest = Column(Integer)
    delta = Column(Float)
    gamma = Column(Float)
    theta = Column(Float)
    vega = Column(Float)
    
    __table_args__ = (
        Index('idx_market_data_symbol_timestamp', 'symbol', 'timestamp'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': str(self.id),
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'source': self.source,
            'implied_volatility': self.implied_volatility,
            'open_interest': self.open_interest,
            'delta': self.delta,
            'gamma': self.gamma,
            'theta': self.theta,
            'vega': self.vega
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MarketData':
        """Create model from dictionary."""
        if 'id' in data:
            data['id'] = UUID(data['id'])
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

class UserSettings(Base):
    """
    User preferences and configuration.
    
    This model stores user-specific settings and preferences for various
    aspects of the system, including trading parameters, UI preferences,
    and notification settings.
    
    Attributes:
        id (UUID): Unique identifier
        category (str): Setting category (e.g., 'trading', 'ui', 'alerts')
        key (str): Setting key
        value (JSON): Setting value (can be any JSON-serializable data)
        last_modified (datetime): Last modification timestamp
    """
    __tablename__ = 'user_settings'
    
    id = Column(SQLUUID, primary_key=True, default=uuid4)
    category = Column(String, nullable=False)
    key = Column(String, nullable=False)
    value = Column(JSON)
    last_modified = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('category', 'key', name='unique_setting'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': str(self.id),
            'category': self.category,
            'key': self.key,
            'value': self.value,
            'last_modified': self.last_modified.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserSettings':
        """Create model from dictionary."""
        if 'id' in data:
            data['id'] = UUID(data['id'])
        if 'last_modified' in data and isinstance(data['last_modified'], str):
            data['last_modified'] = datetime.fromisoformat(data['last_modified'])
        return cls(**data)

class SystemState(Base):
    """
    System state and recovery data.
    
    This model stores the state of various system components for recovery
    and monitoring purposes. It helps maintain system reliability and
    enables state recovery after crashes or restarts.
    
    Attributes:
        id (UUID): Unique identifier
        component (str): Component name (e.g., 'trade_executor', 'market_watcher')
        state (JSON): Component state data
        timestamp (datetime): State update timestamp
        is_active (bool): Whether the component is currently active
    """
    __tablename__ = 'system_state'
    
    id = Column(SQLUUID, primary_key=True, default=uuid4)
    component = Column(String, nullable=False)
    state = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': str(self.id),
            'component': self.component,
            'state': self.state,
            'timestamp': self.timestamp.isoformat(),
            'is_active': self.is_active
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SystemState':
        """Create model from dictionary."""
        if 'id' in data:
            data['id'] = UUID(data['id'])
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

class Analytics(Base):
    """
    Trading analytics and metrics.
    
    This model stores various trading analytics and performance metrics.
    It enables tracking of system performance, risk metrics, and other
    analytical data over time.
    
    Attributes:
        id (UUID): Unique identifier
        category (str): Metric category (e.g., 'performance', 'risk', 'exposure')
        metric (str): Metric name
        value (float): Metric value
        timestamp (datetime): Measurement timestamp
        meta_data (JSON): Additional context and metadata
    """
    __tablename__ = 'analytics'
    
    id = Column(SQLUUID, primary_key=True, default=uuid4)
    category = Column(String, nullable=False)
    metric = Column(String, nullable=False)
    value = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    meta_data = Column(JSON)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the model to a dictionary."""
        return {
            'id': str(self.id),
            'category': self.category,
            'metric': self.metric,
            'value': self.value,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'meta_data': self.meta_data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Analytics':
        """Create a model instance from a dictionary."""
        if 'id' in data:
            data['id'] = UUID(data['id'])
        if 'timestamp' in data and data['timestamp']:
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

class TradingStrategy(Base):
    """
    Model representing a trading strategy configuration.
    
    This model stores trading strategy definitions, including parameters,
    validation rules, and metadata for strategy versioning and tracking.
    
    Attributes:
        strategy_id (UUID): Unique identifier for the strategy
        name (str): Strategy name
        description (str): Detailed strategy description
        parameters (dict): Strategy parameters and settings
        creator (str): Who/what created the strategy
        created_at (datetime): When the strategy was created
        last_modified (datetime): Last modification timestamp
        is_active (bool): Whether the strategy is currently active
        
    Relationships:
        plays: List of plays using this strategy
    """
    
    __tablename__ = 'trading_strategies'
    
    strategy_id = Column(SQLUUID, primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    description = Column(Text)
    parameters = Column(JSON)
    creator = Column(String)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_modified = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    plays = relationship("Play", back_populates="trading_strategy")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the model to a dictionary.
        
        Returns:
            dict: Dictionary representation of the strategy
        """
        return {
            'strategy_id': str(self.strategy_id),
            'name': self.name,
            'description': self.description,
            'parameters': self.parameters,
            'creator': self.creator,
            'created_at': self.created_at.isoformat(),
            'last_modified': self.last_modified.isoformat() if self.last_modified else None,
            'is_active': self.is_active
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradingStrategy':
        """
        Create a model instance from a dictionary.
        
        Args:
            data (dict): Dictionary containing strategy data
            
        Returns:
            TradingStrategy: New TradingStrategy instance
        """
        if 'strategy_id' in data:
            data['strategy_id'] = UUID(data['strategy_id'])
        if 'created_at' in data:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'last_modified' in data and data['last_modified']:
            data['last_modified'] = datetime.fromisoformat(data['last_modified'])
        return cls(**data) 