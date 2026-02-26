import sqlite3, threading, time
from helper import ActiveChat


DATABASE = "database.db"

class ChatHandler:
    TABLE = "reports"
    COL_CHAT_ID = "chat_id"
    COL_NAME = "name"
    COL_SUBJECT = "subject"
    COL_MESSSAGE = "message"
    COL_PHONE = "phone"
    COL_ADDRESS = "address"
    COL_LONGITUDE = "longitude"
    COL_LATITUDE = "latitude"
    COL_STATE = "state"
    COL_REPORT_MESSAGE_ID = "report_message_id"
    COL_CLIENT_MESSAGE_ID = "client_message_id"
    COL_CREATION_TIME = "creation_time"

    def __init__(self, active_age_hours:str, total_age_hours:str):
        # init values
        self.active_chat_age_hours = active_age_hours
        self.total_chat_age_hours = total_age_hours
        self.connection = sqlite3.connect(DATABASE)
        self.cursor = self.connection.cursor()

        # create database table and indexes
        self.cursor.execute(f"""CREATE TABLE IF NOT EXISTS {self.TABLE}(
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            {self.COL_CHAT_ID} TEXT,
                            {self.COL_NAME} TEXT,
                            {self.COL_SUBJECT} TEXT,
                            {self.COL_MESSSAGE} TEXT,
                            {self.COL_PHONE} TEXT,
                            {self.COL_ADDRESS} TEXT,
                            {self.COL_LONGITUDE} REAL,
                            {self.COL_LATITUDE} REAL,
                            {self.COL_STATE} TEXT,
                            {self.COL_CLIENT_MESSAGE_ID} TEXT,
                            {self.COL_REPORT_MESSAGE_ID} TEXT,
                            {self.COL_CREATION_TIME} TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            );""")    
        self.cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_chat_id ON {self.TABLE}({self.COL_CHAT_ID})")
        self.cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_report_id ON {self.TABLE}({self.COL_REPORT_MESSAGE_ID})")
        self.connection.commit()

        self.cleaner = threading.Thread(target=self._deleteOldRecords,args=(self.total_chat_age_hours,), daemon=True)
        self.cleaner.start()

    def _deleteOldRecords(self, life_span):
        cleaner_connection = sqlite3.connect(DATABASE)
        cleaner_cursor = cleaner_connection.cursor()
        while True:
            cleaner_cursor.execute(f"""DELETE FROM {self.TABLE}
                                WHERE {self.COL_CREATION_TIME} < datetime('now', '-{life_span} hour')""")
            cleaner_connection.commit()
            time.sleep(3600) # in seconds

    def saveClientMessageId(self, chat_id, message_id):
        pk = self.getActiveChatPk(chat_id)
        if pk is None:
            # Fallback: use latest chat of this user to avoid runtime crash.
            pk = self._getLatestChatPk(chat_id)
        if pk is None:
            return
        self.cursor.execute(
            f"""UPDATE {self.TABLE}
                SET {self.COL_CLIENT_MESSAGE_ID} = ?
                WHERE id = ?
            """,
            (message_id, pk),
        )
        self.connection.commit()

    def saveReportMessageId(self, chat_id, report_message_id):
        pk = self.getActiveChatPk(chat_id)
        if pk is None:
            # Fallback: use latest chat of this user to avoid runtime crash.
            pk = self._getLatestChatPk(chat_id)
        if pk is None:
            return
        self.cursor.execute(
            f"""UPDATE {self.TABLE}
                SET {self.COL_REPORT_MESSAGE_ID} = ?
                WHERE id = ?
            """,
            (report_message_id, pk),
        )
        self.connection.commit()

    def getChatAndMessageIds(self, report_message_ID)->tuple:
        """Return (chat_id, client_message_id) if available. Return None if there wasn't any record"""
        self.cursor.execute(f"""SELECT "{self.COL_CHAT_ID}","{self.COL_CLIENT_MESSAGE_ID}"
                            FROM "{self.TABLE}"
                            WHERE "{self.COL_REPORT_MESSAGE_ID}" = "{report_message_ID}"
                            """)
        record = self.cursor.fetchone()
        if record:
            return (record[0],record[1])
        return None

    def getActiveChat(self, chat_id):
        """Return active chat if available.
        if there wasn't any chat or it's state is cancelled or closed, it create and return new one"""
        self.cursor.execute(f"""SELECT * 
                            FROM reports
                            WHERE chat_id = "{chat_id}"
                            AND state != "{ActiveChat.States.CANCELLED}"
                            AND state != "{ActiveChat.States.SUBMITTED}"
                            AND {self.COL_CREATION_TIME} > datetime('now', '-{self.active_chat_age_hours} hour')
                            """)
        record = self.cursor.fetchone()
        if record:
            active_chat = ActiveChat(chat_id)
            active_chat.name = record[2]
            active_chat.subject = record[3]
            active_chat.message = record[4]
            active_chat.phone = record[5]
            active_chat.address = record[6]
            active_chat.longitute = record[7]
            active_chat.latitute = record[8]
            active_chat.state = record[9]
        else:
            active_chat = ActiveChat(chat_id)
        return active_chat
    
    def getActiveChatPk(self, chat_id):
        self.cursor.execute(f"""SELECT id 
                            FROM reports
                            WHERE chat_id = ?
                            AND state != ?
                            AND state != ?
                            AND {self.COL_CREATION_TIME} > datetime('now', '-{self.active_chat_age_hours} hour')
                            ORDER BY id DESC
                            LIMIT 1
                            """, (chat_id, ActiveChat.States.CANCELLED, ActiveChat.States.SUBMITTED))
        record = self.cursor.fetchone()
        if record:
            return record[0]
        return None

    def _getLatestChatPk(self, chat_id):
        self.cursor.execute(f"""SELECT id
                            FROM reports
                            WHERE chat_id = ?
                            ORDER BY id DESC
                            LIMIT 1
                            """, (chat_id,))
        record = self.cursor.fetchone()
        if record:
            return record[0]
        return None

    def saveChat(self, chat:ActiveChat):
        pk = self.getActiveChatPk(chat.chat_id)        
        if pk:
            self.cursor.execute(f"""UPDATE "{self.TABLE}"
                                SET ("{self.COL_NAME}",
                                    "{self.COL_SUBJECT}",
                                    "{self.COL_MESSSAGE}",
                                    "{self.COL_PHONE}",
                                    "{self.COL_ADDRESS}",
                                    "{self.COL_LONGITUDE}",
                                    "{self.COL_LATITUDE}",
                                    "{self.COL_STATE}") = 
                                    ("{chat.name}",
                                    "{chat.subject}",
                                    "{chat.message}",
                                    "{chat.phone}",
                                    "{chat.address}",
                                    "{chat.longitute}",
                                    "{chat.latitute}",
                                    "{chat.state}")
                                WHERE id = {pk}
                                AND state != "{ActiveChat.States.CANCELLED}"
                                AND state != "{ActiveChat.States.SUBMITTED}"
                                """)
        else:
            self.cursor.execute(f"""INSERT INTO "{self.TABLE}"
                                ("{self.COL_CHAT_ID}",
                                "{self.COL_NAME}",
                                "{self.COL_SUBJECT}",
                                "{self.COL_MESSSAGE}",
                                "{self.COL_PHONE}",
                                "{self.COL_ADDRESS}",
                                "{self.COL_LONGITUDE}",
                                "{self.COL_LATITUDE}",
                                "{self.COL_STATE}") 
                                VALUES 
                                ("{chat.chat_id}",
                                "{chat.name}",
                                "{chat.subject}",
                                "{chat.message}",
                                "{chat.phone}",
                                "{chat.address}",
                                "{chat.longitute}",
                                "{chat.latitute}",
                                "{chat.state}")
                                """)
        self.connection.commit()

class AdminRequestBanningHandler:
    TABLE = "banned_admin_request"
    COL_CHAT_ID = "chat_id"
    COL_CREATION_TIME = "creation_time"

    def __init__(self, banning_duration_hours:str):
        # init values
        self.banning_duration = banning_duration_hours
        self.connection = sqlite3.connect(DATABASE)
        self.cursor = self.connection.cursor()

        # create database table and indexes
        self.cursor.execute(f"""CREATE TABLE IF NOT EXISTS {self.TABLE}(
                            {self.COL_CHAT_ID} TEXT PRIMARY KEY,
                            {self.COL_CREATION_TIME} TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            );""")    
        self.connection.commit()

        self.cleaner = threading.Thread(target=self._deleteOldRecords, daemon=True)
        self.cleaner.start()

    def setBanningDuration(self, banning_duration_hours:str):
        self.banning_duration = banning_duration_hours

    def _deleteOldRecords(self):
        cleaner_connection = sqlite3.connect(DATABASE)
        cleaner_cursor = cleaner_connection.cursor()
        while True:
            cleaner_cursor.execute(f"""DELETE FROM {self.TABLE}
                                WHERE {self.COL_CREATION_TIME} < datetime('now', '-{self.banning_duration} hour')""")
            cleaner_connection.commit()
            time.sleep(900) # in seconds

    def isBanned(self, chat_id:str)->bool:
        """Return True if banned"""
        self.cursor.execute(f"""SELECT *
                            FROM "{self.TABLE}"
                            WHERE "{self.COL_CHAT_ID}" = "{chat_id}"
                            """)
        record = self.cursor.fetchone()
        if record:
            return True
        return False

    def ban(self, chat_id:str):
        self.cursor.execute(f"""INSERT INTO "{self.TABLE}"
                            ("{self.COL_CHAT_ID}") 
                            VALUES 
                            ("{chat_id}")
                            ON CONFLICT ({self.COL_CHAT_ID})
                            DO UPDATE SET
                            "{self.COL_CREATION_TIME}" = datetime('now')                            
                            """)    
        self.connection.commit()

    def unban(self, chat_id:str):
        self.cursor.execute(f"""DELETE FROM "{self.TABLE}"
                            WHERE "{self.COL_CHAT_ID}" = "{chat_id}"
                            """)    
        self.connection.commit()

if __name__  == "__main__":
    # test
    # a = AdminRequestBanningHandler("1")
    # a.ban("A")
    # a.ban("B")
    # print(a.isBanned("A"),a.isBanned("B"))
    # a.unban("A")
    # print(a.isBanned("A"),a.isBanned("B"))
    pass
