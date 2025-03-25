"""
Migration Script: Recreate WEM Stocks Table with Complete Schema

This script ensures that the wem_stocks table has all required columns
including the 'wem' column. It will:
1. Check if the table exists and has the correct schema
2. If not, it will back up existing data
3. Drop and recreate the table with the full schema
4. Restore any backed up data
"""

import logging
from datetime import datetime
from typing import Dict, List, Any
from sqlalchemy import Table, MetaData, Column, String, Float, Boolean, DateTime, Text, inspect
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

def upgrade():
    """
    Upgrade the database by ensuring the wem_stocks table has all required columns.
    This is a permanent fix that ensures the table structure matches the model definition.
    """
    from goldflipper.database.connection import get_db_connection
    from sqlalchemy import text
    
    logger.info("Starting wem_stocks table schema verification...")
    
    try:
        with get_db_connection() as session:
            engine = session.get_bind()
            
            # Check if wem_stocks table exists
            inspector = inspect(engine)
            if 'wem_stocks' not in inspector.get_table_names():
                logger.info("wem_stocks table doesn't exist, nothing to do. Will be created by SQLAlchemy later.")
                return
            
            # Get existing columns in wem_stocks table
            existing_columns = [column['name'] for column in inspector.get_columns('wem_stocks')]
            logger.info(f"Existing columns in wem_stocks: {existing_columns}")
            
            # Check if 'wem' column exists
            if 'wem' in existing_columns:
                logger.info("The 'wem' column already exists in wem_stocks table, no action needed.")
                return
            
            # Get all data from the table before recreating it
            logger.info("Backing up existing wem_stocks data...")
            result = session.execute(text("SELECT * FROM wem_stocks"))
            rows = result.fetchall()
            
            # Convert to dictionaries for easier handling
            column_names = result.keys()
            data_backup = []
            for row in rows:
                row_dict = {}
                for i, column in enumerate(column_names):
                    row_dict[column] = row[i]
                data_backup.append(row_dict)
            
            logger.info(f"Backed up {len(data_backup)} records from wem_stocks table")
            
            # Drop the existing table
            logger.info("Dropping existing wem_stocks table...")
            session.execute(text("DROP TABLE wem_stocks"))
            session.commit()
            logger.info("Table dropped successfully")
            
            # Create a temporary metadata and table definition
            metadata = MetaData()
            wem_stocks = Table(
                'wem_stocks', metadata,
                Column('id', String, primary_key=True),
                Column('symbol', String, nullable=False),
                Column('is_default', Boolean, default=False),
                Column('atm_price', Float),
                Column('wem', Float),  # Ensure WEM column is included
                Column('straddle_strangle', Float),
                Column('wem_spread', Float),
                Column('delta_16_plus', Float),
                Column('straddle_2', Float),
                Column('straddle_1', Float),
                Column('delta_16_minus', Float),
                Column('delta_range', Float),
                Column('delta_range_pct', Float),
                Column('notes', Text),
                Column('last_updated', DateTime),
                Column('meta_data', Text)  # JSON as text
            )
            
            # Create the table with the new schema
            logger.info("Creating new wem_stocks table with complete schema...")
            metadata.create_all(engine)
            logger.info("Table created successfully")
            
            # Restore data if there was any
            if data_backup:
                logger.info("Restoring backed up data...")
                for record in data_backup:
                    # Convert the record to a format suitable for insertion
                    # Remove fields that don't exist in the new schema or add defaults
                    insert_record = {}
                    for key, value in record.items():
                        if key in existing_columns:
                            insert_record[key] = value
                    
                    # Add missing columns with default values
                    insert_record.setdefault('wem', None)
                    
                    # Convert any JSON data stored as string
                    if 'meta_data' in insert_record and isinstance(insert_record['meta_data'], dict):
                        import json
                        insert_record['meta_data'] = json.dumps(insert_record['meta_data'])
                    
                    # Create insert statement
                    columns = ', '.join(insert_record.keys())
                    placeholders = ', '.join([f":{key}" for key in insert_record.keys()])
                    insert_sql = f"INSERT INTO wem_stocks ({columns}) VALUES ({placeholders})"
                    
                    # Execute insert
                    session.execute(text(insert_sql), insert_record)
                
                session.commit()
                logger.info(f"Successfully restored {len(data_backup)} records to wem_stocks table")
            
            logger.info("wem_stocks table has been successfully recreated with all required columns including 'wem'")
            
    except SQLAlchemyError as e:
        logger.error(f"Database error during wem_stocks table migration: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during wem_stocks table migration: {str(e)}")
        raise 