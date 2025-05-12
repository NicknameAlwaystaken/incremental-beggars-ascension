import aiosqlite
import json
import os

game_data_folder = 'game_data'


async def create_energies_table(db_location):
    async with aiosqlite.connect(db_location) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS energies (
                energy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                max_energy REAL,
                recovery_rate REAL
        )
        ''')
        await db.commit()


async def create_player_energies_table(db_location):
    async with aiosqlite.connect(db_location) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS player_energies (
                player_id INTEGER,
                energy_id INTEGER,
                current_energy REAL,
                PRIMARY KEY (player_id, energy_id),
                FOREIGN KEY (energy_id) REFERENCES energies(energy_id)
        )
        ''')
        await db.commit()


async def create_reputations_table(db_location):
    async with aiosqlite.connect(db_location) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS reputations (
                reputation_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                start_level INTEGER NOT NULL,
                max_level INTEGER NOT NULL,
                base_exp_requirement REAL NOT NULL,
                scaling_factor REAL NOT NULL,
                exp_formula TEXT
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS reputation_titles (
            id INTEGER PRIMARY KEY,
            reputation_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            level INTEGER NOT NULL,
            UNIQUE (reputation_id, level),
            FOREIGN KEY (reputation_id) REFERENCES reputations(reputation_id) ON DELETE CASCADE
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS reputation_unlocks (
            id INTEGER PRIMARY KEY,
            reputation_id INTEGER NOT NULL,
            level INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            UNIQUE (reputation_id, name),
            FOREIGN KEY (reputation_id) REFERENCES reputations(reputation_id) ON DELETE CASCADE
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS reputation_unlock_effects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unlock_id INTEGER NOT NULL,
            effect TEXT NOT NULL,
            UNIQUE (unlock_id, effect),
            FOREIGN KEY (unlock_id) REFERENCES reputation_unlocks(id) ON DELETE CASCADE
        )
        ''')

        await db.commit()


async def create_skills_table(db_location):
    async with aiosqlite.connect(db_location) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS skills (
                skill_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                start_level INTEGER NOT NULL,
                max_level INTEGER NOT NULL,
                base_exp_requirement REAL NOT NULL,
                scaling_factor REAL NOT NULL,
                exp_formula TEXT
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS skill_effects (
            id INTEGER PRIMARY KEY,
            skill_id INTEGER NOT NULL,
            stat TEXT NOT NULL,
            modifier_type TEXT NOT NULL,
            modifier_value REAL NOT NULL,
            UNIQUE (skill_id, stat, modifier_type),
            FOREIGN KEY (skill_id) REFERENCES skills (skill_id) ON DELETE CASCADE
        )
        ''')
        await db.commit()


async def create_player_locations_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS player_locations (
            player_id INTEGER NOT NULL,
            location_id INTEGER NOT NULL,
            PRIMARY KEY (player_id, location_id),
            FOREIGN KEY (location_id) REFERENCES locations(location_id)
        )
        ''')

        await db.commit()


async def create_player_reputations_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS player_reputations (
            player_id INTEGER NOT NULL,
            reputation_id INTEGER NOT NULL,
            current_level INTEGER NOT NULL,
            current_exp REAL NOT NULL,
            PRIMARY KEY (player_id, reputation_id),
            FOREIGN KEY (reputation_id) REFERENCES reputations(reputation_id)
        )
        ''')

        await db.commit()


async def create_player_skills_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS player_skills (
            player_id INTEGER NOT NULL,
            skill_id INTEGER NOT NULL,
            current_level INTEGER NOT NULL,
            current_exp REAL NOT NULL,
            PRIMARY KEY (player_id, skill_id),
            FOREIGN KEY (skill_id) REFERENCES skills(skill_id)
        )
        ''')
        await db.commit()


async def create_player_activities_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS player_activities (
            player_id INTEGER NOT NULL,
            activity_id INTEGER NOT NULL,
            PRIMARY KEY (player_id, activity_id),
            FOREIGN KEY (activity_id) REFERENCES activities(activity_id)
        )
        ''')

        await db.commit()


async def create_locations_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS locations (
            location_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            icon_png TEXT NOT NULL,
            description TEXT NOT NULL
        );
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS location_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER NOT NULL,
            activity TEXT NOT NULL,
            UNIQUE (location_id, activity),
            FOREIGN KEY (location_id) REFERENCES locations(location_id) ON DELETE CASCADE
        );
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS location_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER NOT NULL,
            task TEXT NOT NULL,
            UNIQUE (location_id, task),
            FOREIGN KEY (location_id) REFERENCES locations(location_id) ON DELETE CASCADE
        );
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS location_upgrades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER NOT NULL,
            upgrade TEXT NOT NULL,
            UNIQUE (location_id, upgrade),
            FOREIGN KEY (location_id) REFERENCES locations(location_id) ON DELETE CASCADE
        );
        ''')

        await db.commit()


async def create_activities_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            activity_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            icon TEXT,
            output_item TEXT NOT NULL,
            output_amount REAL NOT NULL,
            energy_type TEXT,
            energy_drain_rate REAL,
            skill TEXT,
            skill_exp_rate REAL,
            unlock_conditions TEXT,
            description TEXT,
            status_description TEXT
        )
        ''')
        await db.commit()


async def create_player_tasks_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS player_tasks (
            player_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            count INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (player_id, task_id),
            FOREIGN KEY (task_id) REFERENCES tasks(task_id)
        )
        ''')
        await db.commit()


async def create_player_upgrades_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS player_upgrades (
            player_id INTEGER NOT NULL,
            upgrade_id INTEGER NOT NULL,
            count INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (player_id, upgrade_id),
            FOREIGN KEY (upgrade_id) REFERENCES upgrades(upgrade_id)
        )
        ''')
        await db.commit()


async def create_tasks_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            icon TEXT,
            task_amount INTEGER,
            description TEXT
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS task_outputs (
            id INTEGER PRIMARY KEY,
            task_id INTEGER NOT NULL,
            output_item TEXT NOT NULL,
            output_amount REAL NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS task_costs (
            id INTEGER PRIMARY KEY,
            task_id INTEGER NOT NULL,
            cost_item TEXT NOT NULL,
            cost_amount REAL NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS task_energy_costs (
            id INTEGER PRIMARY KEY,
            task_id INTEGER NOT NULL,
            energy_type TEXT NOT NULL,
            energy_amount REAL NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS task_unlocks (
            id INTEGER PRIMARY KEY,
            task_id INTEGER NOT NULL,
            condition TEXT NOT NULL,
            UNIQUE (task_id, condition),
            FOREIGN KEY (task_id) REFERENCES tasks (task_id) ON DELETE CASCADE
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS task_effects (
            id INTEGER PRIMARY KEY,
            task_id INTEGER NOT NULL,
            stat TEXT NOT NULL,
            modifier_type TEXT NOT NULL,
            modifier_value REAL NOT NULL,
            UNIQUE (task_id, stat, modifier_type),
            FOREIGN KEY (task_id) REFERENCES tasks (task_id) ON DELETE CASCADE
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS task_unlock_conditions (
            task_id INTEGER,
            condition TEXT,
            PRIMARY KEY (task_id, condition),
            FOREIGN KEY (task_id) REFERENCES tasks (task_id) ON DELETE CASCADE
        )
        ''')

        await db.commit()


async def create_games_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS games (
            game_id INTEGER PRIMARY KEY,
            name TEXT
        )
        ''')

        await db.commit()


async def create_upgrades_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS upgrades (
            upgrade_id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            stat TEXT,
            modifier_type TEXT,
            modifier_value INTEGER,
            cost_material TEXT,
            cost INTEGER,
            max_purchases INTEGER,
            description TEXT
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS upgrade_unlocks (
            id INTEGER PRIMARY KEY,
            upgrade_id INTEGER NOT NULL,
            condition TEXT NOT NULL,
            UNIQUE (upgrade_id, condition),
            FOREIGN KEY (upgrade_id) REFERENCES upgrades (upgrade_id) ON DELETE CASCADE
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS upgrade_effects (
            id INTEGER PRIMARY KEY,
            upgrade_id INTEGER NOT NULL,
            stat TEXT NOT NULL,
            modifier_type TEXT NOT NULL,
            modifier_value REAL NOT NULL,
            UNIQUE (upgrade_id, stat, modifier_type),
            FOREIGN KEY (upgrade_id) REFERENCES upgrades (upgrade_id) ON DELETE CASCADE
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS upgrade_unlock_conditions (
            upgrade_id INTEGER,
            condition TEXT,
            PRIMARY KEY (upgrade_id, condition),
            FOREIGN KEY (upgrade_id) REFERENCES upgrades (upgrade_id) ON DELETE CASCADE
        )
        ''')

        await db.commit()


async def create_player_chips_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS player_chips (
            player_id INTEGER NOT NULL PRIMARY KEY,
            amount DOUBLE NOT NULL DEFAULT 0,
            FOREIGN KEY (player_id) REFERENCES players(player_id)
        )
        ''')
        await db.commit()


async def create_player_games_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS player_games (
            player_id INTEGER NOT NULL,
            game_id INTEGER NOT NULL,
            played DOUBLE NOT NULL DEFAULT 0,
            wins DOUBLE NOT NULL DEFAULT 0,
            losses DOUBLE NOT NULL DEFAULT 0,
            amount_bet DOUBLE NOT NULL DEFAULT 0,
            earnings DOUBLE NOT NULL DEFAULT 0,
            PRIMARY KEY (player_id, game_id),
            FOREIGN KEY (game_id) REFERENCES games(game_id)
        )
        ''')
        await db.commit()


async def create_player_items_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS player_items (
            player_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            amount DOUBLE NOT NULL DEFAULT 0,
            PRIMARY KEY (player_id, item_id),
            FOREIGN KEY (item_id) REFERENCES items(item_id)
        )
        ''')
        await db.commit()


async def create_items_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS items (
            item_id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            default_capacity INTEGER
        )
        ''')
        await db.commit()


async def create_players_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
            CREATE TABLE IF NOT EXISTS players (
                player_id INTEGER PRIMARY KEY,
                player_name TEXT NOT NULL,
                player_display_name TEXT NOT NULL,
                start_date TEXT,
                last_update_time TEXT
            )
        ''')
        await db.commit()


async def create_server_channel_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
            CREATE TABLE IF NOT EXISTS servers (
                server_id BIGINT PRIMARY KEY,
                server_name TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                channel_id BIGINT PRIMARY KEY,
                server_id BIGINT,
                channel_name TEXT,
                FOREIGN KEY (server_id) REFERENCES servers(server_id)
            )
        ''')
        await db.commit()


async def update_energies_from_json_to_db(database_location):
    with open(os.path.join(game_data_folder, 'energies.json'), encoding='utf-8') as file:
        energies_data = json.load(file)

    async with aiosqlite.connect(database_location) as db:
        for energy in energies_data:
            await db.execute('''
                INSERT OR REPLACE INTO energies (energy_id, name, max_energy, recovery_rate)
                VALUES (?, ?, ?, ?)
            ''', (energy['id'], energy['name'], energy['max_energy'], energy['recovery_rate']))
        await db.commit()


async def update_games_from_json_to_db(database_location):
    with open(os.path.join(game_data_folder, 'games.json'), encoding='utf-8') as file:
        games_data = json.load(file)

    async with aiosqlite.connect(database_location) as db:
        for game in games_data:
            await db.execute('''
                INSERT OR REPLACE INTO games (game_id, name)
                VALUES (?, ?)
            ''', (game['id'], game['name']))

            await db.commit()


async def update_locations_from_json_to_db(database_location):
    with open(os.path.join(game_data_folder, 'locations.json'), encoding='utf-8') as file:
        locations = json.load(file)

    async with aiosqlite.connect(database_location) as db:
        for location in locations:

            await db.execute('''
                INSERT OR REPLACE INTO locations (location_id, name, icon_png, description)
                VALUES (?, ?, ?, ?)
            ''', (location["id"], location["name"], location["icon_png"], location["description"]))

            for activity in location.get("activities", []):
                await db.execute('''
                    INSERT OR IGNORE INTO location_activities (location_id, activity)
                    VALUES (?, ?)
                ''', (location["id"], activity))

            for task in location.get("tasks", []):
                await db.execute('''
                    INSERT OR IGNORE INTO location_tasks (location_id, task)
                    VALUES (?, ?)
                ''', (location["id"], task))

            for upgrade in location.get("upgrades", []):
                await db.execute('''
                    INSERT OR IGNORE INTO location_upgrades (location_id, upgrade)
                    VALUES (?, ?)
                ''', (location["id"], upgrade))

        await db.commit()


async def update_reputations_from_json_to_db(database_location):
    with open(os.path.join(game_data_folder, 'reputation.json'), encoding='utf-8') as file:
        reputation = json.load(file)

    async with aiosqlite.connect(database_location) as db:
        if reputation:
            await db.execute('''
                INSERT OR REPLACE INTO reputations (reputation_id, name, description, start_level, max_level, base_exp_requirement, scaling_factor, exp_formula)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (reputation['id'], reputation['name'], reputation['description'], reputation['start_level'], reputation['max_level'], reputation['base_exp_requirement'], reputation['scaling_factor'], reputation['exp_formula']))

        await db.commit()


async def update_reputations_unlocks_from_json_to_db(database_location):
    with open(os.path.join(game_data_folder, 'reputation_unlocks.json'), encoding='utf-8') as file:
        unlocks = json.load(file)

    async with aiosqlite.connect(database_location) as db:
        for unlock in unlocks:
            await db.execute('''
                INSERT OR REPLACE INTO reputation_unlocks (
                    id, reputation_id, level, name, description
                )
                VALUES (?, ?, ?, ?, ?)
            ''', (
                unlock['id'],
                unlock['reputation_id'],
                unlock['level'],
                unlock['name'],
                unlock['description']
            ))

            # Delete old effects, replace with new
            await db.execute('DELETE FROM reputation_unlock_effects WHERE unlock_id = ?', (unlock['id'],))

            for effect in unlock.get('unlocks', []):
                await db.execute('''
                    INSERT INTO reputation_unlock_effects (unlock_id, effect)
                    VALUES (?, ?)
                ''', (
                    unlock['id'],
                    effect
                ))

        await db.commit()


async def update_reputations_titles_from_json_to_db(database_location):
    with open(os.path.join(game_data_folder, 'reputation_titles.json'), encoding='utf-8') as file:
        titles = json.load(file)

    async with aiosqlite.connect(database_location) as db:
        for title in titles:
            await db.execute('''
                INSERT OR REPLACE INTO reputation_titles (
                    id, reputation_id, name, level
                ) VALUES (?, ?, ?, ?)
            ''', (
                title['id'],
                title['reputation_id'],
                title['name'],
                title['level']
            ))

        await db.commit()


async def update_skills_from_json_to_db(database_location):
    with open(os.path.join(game_data_folder, 'skills.json'), encoding='utf-8') as file:
        skills_data = json.load(file)

    async with aiosqlite.connect(database_location) as db:
        for skill in skills_data:
            await db.execute('''
                INSERT OR REPLACE INTO skills (skill_id, name, description, start_level, max_level, base_exp_requirement, scaling_factor, exp_formula)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (skill['id'], skill['name'], skill['description'], skill['start_level'], skill['max_level'], skill['base_exp_requirement'], skill['scaling_factor'], skill['exp_formula']))

            if 'effects' in skill and skill['effects']:
                for stat, effect in skill['effects'].items():
                    await db.execute('''
                        INSERT OR REPLACE INTO skill_effects (
                            skill_id, stat, modifier_type, modifier_value
                        )
                        VALUES (?, ?, ?, ?)
                    ''', (
                        skill['id'], stat, effect['modifier_type'], effect['modifier_value']
                    ))

        await db.commit()


async def update_activities_from_json_to_db(database_location):
    with open(os.path.join(game_data_folder, 'activities.json'), encoding='utf-8') as file:
        activities = json.load(file)

    async with aiosqlite.connect(database_location) as db:
        for activity in activities:
            await db.execute('''
                INSERT OR REPLACE INTO activities (activity_id, name, icon, output_item, output_amount, energy_type, energy_drain_rate, skill, skill_exp_rate, unlock_conditions, description, status_description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (activity['id'], activity['name'], activity['icon'],
                  activity['output_item'], activity['output_amount'],
                  activity['energy_type'],
                  activity['energy_drain_rate'],
                  activity['skill'],
                  activity['skill_exp_rate'],
                  ','.join(activity['unlock_conditions']),
                  activity['description'],
                  activity['status_description']))
        await db.commit()


async def update_items_from_json_to_db(database_location):
    with open(os.path.join(game_data_folder, 'items.json')) as file:
        items = json.load(file)

    async with aiosqlite.connect(database_location) as db:
        for item in items:
            await db.execute('''
                INSERT OR REPLACE INTO items (item_id, name, default_capacity)
                VALUES (?, ?, ?)
            ''', (item['id'], item['name'], item['capacity']))

        await db.commit()


async def update_tasks_from_json_to_db(database_location):
    with open(os.path.join(game_data_folder, 'tasks.json'), encoding='utf-8') as file:
        tasks = json.load(file)

    async with aiosqlite.connect(database_location) as db:
        for task in tasks:
            await db.execute('''
                INSERT OR REPLACE INTO tasks (task_id, name, icon,
                task_amount, description)
                VALUES (?, ?, ?, ?, ?)
            ''', (task['id'], task['name'], task['icon'],
                  task['task_amount'],  task['description']))

            await db.execute('DELETE FROM task_outputs WHERE task_id = ?', (task['id'],))
            for output in task['outputs']:
                await db.execute('''
                    INSERT INTO task_outputs (task_id, output_item, output_amount)
                    VALUES (?, ?, ?)
                ''', (task['id'], output['item'], output['amount']))

            await db.execute('DELETE FROM task_costs WHERE task_id = ?', (task['id'],))
            for cost in task['costs']:
                await db.execute('''
                    INSERT INTO task_costs (task_id, cost_item, cost_amount)
                    VALUES (?, ?, ?)
                ''', (task['id'], cost['item'], cost['amount']))

            await db.execute('DELETE FROM task_energy_costs WHERE task_id = ?', (task['id'],))
            for energy_cost in task['energy_costs']:
                await db.execute('''
                    INSERT INTO task_energy_costs (task_id, energy_type, energy_amount)
                    VALUES (?, ?, ?)
                ''', (task['id'], energy_cost['energy'], energy_cost['amount']))

            if 'effects' in task and task['effects']:
                for stat, effect in task['effects'].items():
                    await db.execute('''
                        INSERT OR REPLACE INTO task_effects (
                            task_id, stat, modifier_type, modifier_value
                        )
                        VALUES (?, ?, ?, ?)
                    ''', (
                        task['id'], stat, effect['modifier_type'], effect['modifier_value']
                    ))

            if task['unlocks']:
                for condition in task['unlocks']:
                    async with db.execute('''
                        SELECT 1 FROM task_unlocks WHERE task_id = ? AND condition = ?
                    ''', (task['id'], condition)) as cursor:
                        exists = await cursor.fetchone()

                    if not exists:
                        await db.execute('''
                            INSERT OR REPLACE INTO task_unlocks (task_id, condition)
                            VALUES (?, ?)
                        ''', (task['id'], condition))

            if task['unlock_conditions']:
                for condition in task['unlock_conditions']:
                    async with db.execute('''
                        SELECT 1 FROM task_unlock_conditions WHERE task_id = ? AND condition = ?
                    ''', (task['id'], condition)) as cursor:
                        exists = await cursor.fetchone()

                    if not exists:
                        await db.execute('''
                            INSERT OR REPLACE INTO task_unlock_conditions (task_id, condition)
                            VALUES (?, ?)
                        ''', (task['id'], condition))

            await db.commit()


async def update_upgrades_from_json_to_db(database_location):
    with open(os.path.join(game_data_folder, 'upgrades.json')) as file:
        upgrades = json.load(file)

    async with aiosqlite.connect(database_location) as db:
        for upgrade in upgrades:
            await db.execute('''
                INSERT OR REPLACE INTO upgrades (upgrade_id, name,
                cost_material, cost, max_purchases,
                description)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (upgrade['id'], upgrade['name'],
                  upgrade['cost_material'], upgrade['cost'],
                  upgrade['max_purchases'], upgrade['description']))

            if 'effects' in upgrade and upgrade['effects']:
                for stat, effect in upgrade['effects'].items():
                    await db.execute('''
                        INSERT OR REPLACE INTO upgrade_effects (
                            upgrade_id, stat, modifier_type, modifier_value
                        )
                        VALUES (?, ?, ?, ?)
                    ''', (
                        upgrade['id'], stat, effect['modifier_type'], effect['modifier_value']
                    ))

            if upgrade['unlocks']:
                for condition in upgrade['unlocks']:
                    async with db.execute('''
                        SELECT 1 FROM upgrade_unlocks WHERE upgrade_id = ? AND condition = ?
                    ''', (upgrade['id'], condition)) as cursor:
                        exists = await cursor.fetchone()

                    if not exists:
                        await db.execute('''
                            INSERT OR REPLACE INTO upgrade_unlocks (upgrade_id, condition)
                            VALUES (?, ?)
                        ''', (upgrade['id'], condition))

            if upgrade['unlock_conditions']:
                for condition in upgrade['unlock_conditions']:
                    async with db.execute('''
                        SELECT 1 FROM upgrade_unlock_conditions WHERE upgrade_id = ? AND condition = ?
                    ''', (upgrade['id'], condition)) as cursor:
                        exists = await cursor.fetchone()

                    if not exists:
                        await db.execute('''
                            INSERT OR REPLACE INTO upgrade_unlock_conditions (upgrade_id, condition)
                            VALUES (?, ?)
                        ''', (upgrade['id'], condition))

            await db.commit()


async def update_player_upgrades(db, player_id, player_upgrades):
    placeholders_upgrades = ', '.join('?' for _ in player_upgrades)

    # Clear all upgrades that player doesn't have anymore
    if player_upgrades:
        query = f"DELETE FROM player_upgrades WHERE player_id = ? AND upgrade_id NOT IN ({placeholders_upgrades})"
        params_upgrades = [player_id] + [upgrade[0] for upgrade in player_upgrades]
        await db.execute(query, params_upgrades)
    else:
        await db.execute("DELETE FROM player_upgrades WHERE player_id = ?", (player_id,))

    # Add or update changed upgrades
    for player_upgrade in player_upgrades:
        await db.execute('''
            INSERT OR REPLACE INTO player_upgrades (player_id, upgrade_id, count)
            VALUES (?, ?, ?)
        ''', (player_id, player_upgrade[0], player_upgrade[1]))


async def update_player_items(db, player_id, player_items):
    placeholders_items = ', '.join('?' for _ in player_items)

    # Clear all items that player doesn't have anymore
    if player_items:
        query = f"DELETE FROM player_items WHERE player_id = ? AND item_id NOT IN ({placeholders_items})"
        params_items = [player_id] + [item[0] for item in player_items]
        await db.execute(query, params_items)
    else:
        await db.execute("DELETE FROM player_items WHERE player_id = ?", (player_id,))

    # Add or update changed items
    for player_item in player_items:
        await db.execute('''
            INSERT OR REPLACE INTO player_items (player_id, item_id, amount)
            VALUES (?, ?, ?)
        ''', (player_id, player_item[0], player_item[1]))


async def update_player_chips(db, player_id, player_chips):
    await db.execute('''
        INSERT OR REPLACE INTO player_chips (player_id, amount)
        VALUES (?, ?)
    ''', (player_id, player_chips))


async def update_player_games(db, player_id, player_games):
    for player_game in player_games:
        await db.execute('''
            INSERT OR REPLACE INTO player_games (player_id, game_id, played, wins, losses, amount_bet, earnings)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (player_id, player_game[0], player_game[1], player_game[2], player_game[3], player_game[4], player_game[5]))


async def update_player_energies(db, player_id, player_energies):
    placeholders_energies = ', '.join('?' for _ in player_energies)

    # Clear all energies that the player doesn't have anymore
    if player_energies:
        query = f"DELETE FROM player_energies WHERE player_id = ? AND energy_id NOT IN ({placeholders_energies})"
        params_energies = [player_id] + [energy[0] for energy in player_energies]
        await db.execute(query, params_energies)
    else:
        await db.execute("DELETE FROM player_energies WHERE player_id = ?", (player_id,))

    # Add or update the player's energies
    for energy_id, current_energy in player_energies:
        await db.execute('''
            INSERT OR REPLACE INTO player_energies (player_id, energy_id, current_energy)
            VALUES (?, ?, ?)
        ''', (player_id, energy_id, current_energy))


async def update_player_reputation(db, player_id, player_reputations):
    # Add or update the player's reputations
    for reputation_id, current_level, current_exp in player_reputations:
        await db.execute('''
            INSERT OR REPLACE INTO player_reputations (player_id, reputation_id, current_level, current_exp)
            VALUES (?, ?, ?, ?)
        ''', (player_id, reputation_id, current_level, current_exp))


async def update_player_skills(db, player_id, player_skills):
    placeholders_skills = ', '.join('?' for _ in player_skills)

    # Clear all skills that the player doesn't have anymore
    if player_skills:
        query = f"DELETE FROM player_skills WHERE player_id = ? AND skill_id NOT IN ({placeholders_skills})"
        params_skills = [player_id] + [skill[0] for skill in player_skills]
        await db.execute(query, params_skills)
    else:
        await db.execute("DELETE FROM player_skills WHERE player_id = ?", (player_id,))

    # Add or update the player's skills
    for skill_id, current_level, current_exp in player_skills:
        await db.execute('''
            INSERT OR REPLACE INTO player_skills (player_id, skill_id, current_level, current_exp)
            VALUES (?, ?, ?, ?)
        ''', (player_id, skill_id, current_level, current_exp))


async def update_player_locations(db, player_id, player_location):
    # Clear all locations that player doesn't have anymore
    if player_location is not None:
        query = "DELETE FROM player_locations WHERE player_id = ? AND location_id != ?"
        params_locations = [player_id, player_location.id]
        await db.execute(query, params_locations)
    else:
        await db.execute("DELETE FROM player_locations WHERE player_id = ?", (player_id,))

    # Add or update changed locations
    if player_location:
        await db.execute('''
            INSERT OR REPLACE INTO player_locations (player_id, location_id)
            VALUES (?, ?)
        ''', (player_id, player_location.id))


async def update_player_activities(db, player_id, player_activity):
    # Clear all activities that player doesn't have anymore
    if player_activity is not None:
        query = "DELETE FROM player_activities WHERE player_id = ? AND activity_id != ?"
        params_activities = [player_id, player_activity.id]
        await db.execute(query, params_activities)
    else:
        await db.execute("DELETE FROM player_activities WHERE player_id = ?", (player_id,))

    # Add or update changed activities
    if player_activity:
        await db.execute('''
            INSERT OR REPLACE INTO player_activities (player_id, activity_id)
            VALUES (?, ?)
        ''', (player_id, player_activity.id))


async def update_player_data(db, player_id, player):
    # Check if the player exists in the database
    async with db.execute('SELECT 1 FROM players WHERE player_id = ?', (player_id,)) as cursor:
        found_player = await cursor.fetchone()

    if found_player:
        await db.execute('''
        UPDATE players
        SET player_display_name = ?, start_date = ?, last_update_time = ?
        WHERE player_id == ?
        ''', (player.display_name, player.start_date, player.last_update_time, player_id))
    else:
        await db.execute('''
        INSERT INTO players (player_id, player_name, player_display_name, start_date, last_update_time)
        VALUES (?, ?, ?, ?, ?)
        ''', (player_id, player.name, player.display_name, player.start_date, player.last_update_time))
