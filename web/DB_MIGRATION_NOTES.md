# GoldFlipper Database Migration Notes

## Overview
Migration from file-based storage to DuckDB for improved reliability, performance, and maintainability.

## Phase 1: Setup & Infrastructure (Current)
- [ ] Database Setup:
  1. Add DuckDB to Poetry dependencies
  2. Configure database location and settings
  3. Create database initialization script
  4. Add database connection management
  5. Implement connection pooling
  6. Add database backup procedures

- [ ] Schema Implementation:
  1. Create core tables:
     - plays (main play information)
     - play_status_history (status changes)
     - trade_logs (execution details)
     - market_data (optional: for caching market data)
  2. Add indexes for common queries
  3. Implement constraints and triggers
  4. Create views for common queries
  5. Add audit logging

- [ ] Migration Tools:
  1. Create data migration scripts
  2. Implement validation tools
  3. Add rollback procedures
  4. Create data verification tools
  5. Add progress tracking

## Phase 2: Core Implementation
- [ ] Database Access Layer:
  1. Create database connection manager
  2. Implement connection pooling
  3. Add transaction management
  4. Create base CRUD operations
  5. Implement query builders
  6. Add error handling and logging

- [ ] Data Models:
  1. Create Play model
  2. Create TradeLog model
  3. Create StatusHistory model
  4. Implement model relationships
  5. Add data validation
  6. Create model factories

- [ ] Repository Layer:
  1. Implement PlayRepository
  2. Create TradeLogRepository
  3. Add StatusHistoryRepository
  4. Create query methods
  5. Implement caching
  6. Add bulk operations

## Phase 3: Integration
- [ ] Core Function Updates:
  1. Modify play creation
  2. Update play status management
  3. Revise trade logging
  4. Update market data handling
  5. Modify conditional play handling
  6. Update batch operations

- [ ] File System Integration:
  1. Create file import tools
  2. Implement export functionality
  3. Add backup procedures
  4. Create archive management
  5. Add file cleanup tools

- [ ] Testing & Validation:
  1. Create unit tests
  2. Add integration tests
  3. Implement performance tests
  4. Add stress testing
  5. Create data validation tools
  6. Add monitoring tools

## Phase 4: Optimization & Cleanup
- [ ] Performance Optimization:
  1. Optimize queries
  2. Add indexes
  3. Implement caching
  4. Add connection pooling
  5. Optimize bulk operations
  6. Add query logging

- [ ] Code Cleanup:
  1. Remove old file operations
  2. Update documentation
  3. Clean up imports
  4. Remove deprecated code
  5. Update error handling
  6. Standardize logging

## Phase 5: Deployment & Monitoring
- [ ] Deployment:
  1. Update PyInstaller spec
  2. Add database migration scripts
  3. Create deployment procedures
  4. Add rollback procedures
  5. Update service scripts
  6. Add health checks

- [ ] Monitoring & Maintenance:
  1. Add performance monitoring
  2. Implement error tracking
  3. Create maintenance scripts
  4. Add backup procedures
  5. Implement recovery tools
  6. Add alerting system

## Technical Details

### Database Schema
```sql
-- Core Tables

CREATE TABLE plays (
    play_id UUID PRIMARY KEY,
    play_name VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    trade_type VARCHAR NOT NULL,
    strike_price DECIMAL(10,2) NOT NULL,
    expiration_date DATE NOT NULL,
    contracts INTEGER NOT NULL,
    status VARCHAR NOT NULL,
    play_class VARCHAR NOT NULL,
    creation_date TIMESTAMP NOT NULL,
    option_contract_symbol VARCHAR,
    entry_point JSON,
    take_profit JSON,
    stop_loss JSON,
    strategy VARCHAR,
    creator VARCHAR,
    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_status CHECK (status IN ('new', 'open', 'closed', 'expired'))
);

CREATE TABLE play_status_history (
    history_id UUID PRIMARY KEY,
    play_id UUID REFERENCES plays(play_id),
    status VARCHAR NOT NULL,
    order_id VARCHAR,
    order_status VARCHAR,
    position_exists BOOLEAN,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closing_order_id VARCHAR,
    closing_order_status VARCHAR,
    contingency_order_id VARCHAR,
    contingency_order_status VARCHAR,
    conditionals_handled BOOLEAN DEFAULT FALSE
);

CREATE TABLE trade_logs (
    trade_id UUID PRIMARY KEY,
    play_id UUID REFERENCES plays(play_id),
    datetime_open TIMESTAMP,
    datetime_close TIMESTAMP,
    price_open DECIMAL(10,2),
    price_close DECIMAL(10,2),
    premium_open DECIMAL(10,2),
    premium_close DECIMAL(10,2),
    delta_open DECIMAL(10,4),
    theta_open DECIMAL(10,4),
    close_type VARCHAR,
    close_condition VARCHAR,
    profit_loss DECIMAL(10,2),
    profit_loss_pct DECIMAL(10,2)
);

-- Indexes

CREATE INDEX idx_plays_status ON plays(status);
CREATE INDEX idx_plays_symbol ON plays(symbol);
CREATE INDEX idx_plays_expiration ON plays(expiration_date);
CREATE INDEX idx_status_history_play ON play_status_history(play_id);
CREATE INDEX idx_trade_logs_play ON trade_logs(play_id);
```

### Migration Strategy
1. **Initial Setup**:
   - Add DuckDB to Poetry dependencies
   - Create database initialization scripts
   - Set up connection management

2. **Data Migration**:
   - Create migration scripts for each data type
   - Implement validation checks
   - Add rollback procedures

3. **Parallel Operation**:
   - Run both systems simultaneously
   - Validate data consistency
   - Monitor performance

4. **Switchover**:
   - Gradually move operations to database
   - Keep file backups
   - Monitor for issues

### Backup & Recovery
1. **Backup Strategy**:
   - Regular database dumps
   - Transaction logging
   - Point-in-time recovery

2. **Recovery Procedures**:
   - Database restoration
   - Transaction replay
   - Data validation

### Performance Considerations
1. **Optimization**:
   - Query optimization
   - Index management
   - Connection pooling

2. **Monitoring**:
   - Query performance
   - Resource usage
   - Error tracking

## Lessons Learned
(To be filled as we progress)

## Next Steps
1. Add DuckDB to Poetry dependencies
2. Create initial database schema
3. Implement connection management
4. Begin data migration tools 