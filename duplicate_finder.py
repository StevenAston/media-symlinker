# duplicate_finder.py

import logging
from database import get_db_connection

def identify_and_link_duplicates():
    """
    Finds files with matching hashes across download/media sources
    and updates the database to link them as duplicates.
    """
    logging.info("Searching for confirmed duplicates based on file hashes...")

    # This SQL query finds pairs of files (one 'downloads', one 'media')
    # that have the exact same hash, but are not yet linked.
    # It ensures we don't try to link a file to itself and that the hash is not null.
    sql_find_matches = """
    SELECT
        d.id as download_file_id,
        m.id as media_file_id
    FROM
        files d
    JOIN
        files m ON d.xxh128_hash = m.xxh128_hash
    WHERE
        d.scan_source = 'downloads'
        AND m.scan_source = 'media'
        AND d.xxh128_hash IS NOT NULL
        AND d.id != m.id
        AND d.status = 'hashed'; -- Only process files that haven't been linked yet
    """

    update_plan = []
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql_find_matches)
            duplicate_pairs = cursor.fetchall()

            if not duplicate_pairs:
                logging.info("No new duplicate pairs found.")
                return 0 # Return 0 found

            logging.info(f"Found {len(duplicate_pairs)} new duplicate file pairs to process.")
            
            for pair in duplicate_pairs:
                update_plan.append((
                    'duplicate_found',
                    pair['media_file_id'],
                    pair['download_file_id']
                ))

            # Batch update the database based on the plan
            update_sql = "UPDATE files SET status = ?, duplicate_of_id = ? WHERE id = ?"
            conn.executemany(update_sql, update_plan)
            conn.commit()
            
            logging.info(f"Successfully marked {len(update_plan)} files as duplicates in the database.")
            return len(update_plan)

    except Exception as e:
        logging.error(f"An error occurred while linking duplicates: {e}")
        return 0