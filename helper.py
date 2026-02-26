import asyncio
import time
from pathlib import Path
from bale import Bot, Update, Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from bale.ui import MenuKeyboardMarkup,MenuKeyboardButton     
from file_manager import Messages, QuickResponses, Subjects, Preferences


BASE_DIR = Path(__file__).resolve().parent

class ActiveChat:
    class States:
            NEW = "جدید"				    # in this state bot will say hello and send subject
            SUBJECT = "دریافت موضوع"   		# in this state subject will be saved and bot asks for location or address or cancell or restart if it's criticism bot will ask for contact or message based on settings
            ADDRESS = "دریافت آدرس"			# in this state address will be saved and bot asks for contact or cancell or restart
            CONTACT = "دریافت اطلاعات تماس"	 # in this state contact will be saved and bot asks for message or cancell or restart
            MESSAGE = "دریافت پیام"			# in this state message will be saved and bot asks for approve or cancell or restart
            APPROVE = "تأیید کردن"		    # in this state data will be cancelled or submitted
            SUBMITTED = "ثبت شده"		    # in this state data will be sent to target group and be saved in logs and send message to client and send start button
            CANCELLED = "لغو شده"		    # in this state data will be saved in logs and send message to client and send start button

    def __init__(self, id:str):
        self.chat_id = id
        self.state = self.States.NEW
        self.name = ""
        self.subject = ""
        self.latitute = ""
        self.longitute = ""
        self.address = ""
        self.phone = ""
        self.message = ""

    def getDataInPersian(self):
        data = dict()
        if self.state : data["وضعیت"]=self.state
        if self.name : data["تماس گیرنده"]=self.name
        if self.subject : data["موضوع"]=self.subject
        if self.latitute and self.longitute : data["موقعیت مکانی"]=(self.longitute, self.latitute)
        if self.address : data["آدرس"]=self.address
        if self.phone : data["شماره تماس"]=self.phone
        if self.message : data["پیام"]=self.message
        return data
    
    def __str__(self):
        data = ""
        if self.name: data+=f"تماس گیرنده {self.name} با شماره تماس {self.phone}\n\n"
        data+= f"موضوع: {self.subject}\n"
        data+= f"شرح:\n {self.message}\n\n"            
        if self.latitute and self.longitute : data+= f"موقعیت مکانی:\n({self.longitute}, {self.latitute})\n"
        if self.address: data+= f"آدرس:\n{self.address}\n"
        return data            

class DictionaryLogger:
    """
    This class helps to save dictionaries as log. use saveLog method to save dictionary in
    defined folder. this methad create a file for each day
    """
    def __init__(self, folder):
        self.log_folder = BASE_DIR / folder
        self.log_folder.mkdir(parents=True, exist_ok=True)

    def saveLog(self, dictionary, filename:str=""):            
            _date = f"{time.localtime()[0]}-{time.localtime()[1]}-{time.localtime()[2]}"
            _time = f"{time.localtime()[3]}:{time.localtime()[4]}:{time.localtime()[5]}"
            
            if not filename:
                filename = _date

            file = self.log_folder / f"{filename}.log"

            with open(file, "a", encoding="utf-8") as log:
                log.write(f"\n{'-'*10}\n{_time}\n")   # seperator and time
                
                for k in dictionary:
                    log.write(f"\n{k}:\n{dictionary[k]}\n")

                log.write("\n")

class Menu:
    APPROVE = "✅ تأیید کردن"
    RESTART = "🔄 شروع مجدد"
    CANCEL = "❌ لغو کردن"
    SEND_LOCATION = "📍 ارسال لوکیشن"
    SEND_CONTACT = "📞 ارسال شماره تماس"
    def __init__(self):
        self._start = MenuKeyboardButton(self.RESTART)
        self._cancel = MenuKeyboardButton(self.CANCEL)
        self._approve = MenuKeyboardButton(self.APPROVE)
        self._location = MenuKeyboardButton(self.SEND_LOCATION,request_location=True)
        self._contact = MenuKeyboardButton(self.SEND_CONTACT,request_contact=True)        

    def start_only(self):
        keyboard = MenuKeyboardMarkup()
        keyboard.add(self._start)
        return keyboard

    def start_cancel(self):
        keyboard = MenuKeyboardMarkup()
        keyboard.add(self._start,row=2)
        keyboard.add(self._cancel,row=2)
        return keyboard	

    def location(self):
        keyboard = self.start_cancel()
        keyboard.add(self._location,row=1)
        return keyboard

    def contact(self):
        keyboard = self.start_cancel()
        keyboard.add(self._contact,row=1)
        return keyboard
    
    def approve(self):
        keyboard = self.start_cancel()
        keyboard.add(self._approve,row=1)
        return keyboard

class PasswordManager:
    def __init__(self, password):
        self._password = password
        self.tries = dict() # {chat_id: tries}          

    def check(self, chat_id:str, password:str)->str:
        tries = self.tries.get(chat_id)
        if password == self._password:
            self.tries.pop(chat_id, None)
            return "Granted"
        elif tries:
            if tries >= 3:
                return "Ban"
            else:
                self.tries[chat_id] += 1
                return "Retry"                
        else:
            self.tries[chat_id]=1
            return "Retry"

    def reset(self, chat_id: str):
        self.tries.pop(chat_id, None)

    def setPassword(self, password: str):
        self._password = password

class BotHandler(Bot):
    def __init__(self, token, **kwargs):
        super().__init__(token, **kwargs)
        self._temporary_messages_id = dict()
    
    async def sendTemporaryMessage(self, chat_id:str, message:str, components=None):
        """
        using this method you can send Message and add message id to message cleaner automatically
        @param component: you can give InlineKeyboardMarkup or MenuKeyboardMarkup object 
        """
        message_id = (await self.send_message(chat_id, message, components=components)).message_id
        self._temporary_messages_id[chat_id] = message_id

    async def sendMenu(self, chat_id:str, components:MenuKeyboardMarkup):
        """
        this method will send a menu.
        """
        await self.send_message(chat_id, "Updating menu...", components=components, delete_after=0.01)       

    async def cleanUp(self, chat_id):
        if self._temporary_messages_id.get(chat_id):
            try:
                await self.delete_message(chat_id,self._temporary_messages_id[chat_id])
            except:
                pass
            try:
                self._temporary_messages_id.pop(chat_id)
            except:
                pass  

class AdminView:
    """
    Admin panel state machine.
    State is stored per chat to avoid cross-user interference.
    """
    BTN_PREFIX = "BTN:"

    PAGE_MAIN = "main"
    PAGE_MESSAGES = "messages"
    PAGE_ASK_FOR_MESSAGE = "ask_message"
    PAGE_QUICK_RESPONSE = "quick_response"
    PAGE_ADD_CRITICISM_QUICK_RESPONSE = "add_criticism_quick"
    PAGE_EDIT_CRITICISM_QUICK_RESPONSE = "edit_criticism_quick"
    PAGE_REMOVE_CRITICISM_QUICK_RESPONSE = "remove_criticism_quick"
    PAGE_ADD_REPORT_QUICK_RESPONSE = "add_report_quick"
    PAGE_EDIT_REPORT_QUICK_RESPONSE = "edit_report_quick"
    PAGE_REMOVE_REPORT_QUICK_RESPONSE = "remove_report_quick"
    PAGE_EDIT_SUBJECTS = "edit_subjects"
    PAGE_EDIT_SUBJECT = "edit_subject"
    PAGE_ADD_SUBJECT = "add_subject"
    PAGE_REMOVE_SUBJECT = "remove_subject"
    PAGE_DEFINED_TEXT_SUBJECT = "defined_text_subject"
    PAGE_DEFINED_TEXT_ACTION = "defined_text_action"
    PAGE_DEFINED_TEXT_ADD = "defined_text_add"
    PAGE_DEFINED_TEXT_EDIT_SELECT = "defined_text_edit_select"
    PAGE_DEFINED_TEXT_EDIT_INPUT = "defined_text_edit_input"
    PAGE_DEFINED_TEXT_REMOVE_SELECT = "defined_text_remove_select"
    PAGE_SETTINGS = "settings"
    PAGE_SETTING_INPUT = "setting_input"
    PAGE_CHAT_HISTORY = "chat_history"

    #.callback_data
    BTN_MAIN_MENU = InlineKeyboardButton("منو اصلی", callback_data="BTN:MAIN_MENU")
    BTN_RETURN = InlineKeyboardButton("بازگشت", callback_data="BTN:RETURN")

    BTN_EDIT_MESSAGES = InlineKeyboardButton("ویرایش پیام‌ها", callback_data="BTN:EDIT_MESSAGES")

    BTN_EDIT_QUICK_RESPONSE = InlineKeyboardButton("ویرایش پاسخ سریع",callback_data="BTN:EDIT_QUICK_RESPONSE")
    BTN_ADD_CRITICISM_QUICK_RESPONSE = InlineKeyboardButton("اضافه کردن پاسخ انتقاد", callback_data="BTN:add_criticism_response")
    BTN_EDIT_CRITICISM_QUICK_RESPONSE = InlineKeyboardButton("ویرایش پاسخ انتقاد", callback_data="BTN:edit_criticism_response")
    BTN_REMOVE_CRITICISM_QUICK_RESPONSE = InlineKeyboardButton("حذف پاسخ انتقاد", callback_data="BTN:remove_criticism_response")
    BTN_ADD_REPORT_QUICK_RESPONSE = InlineKeyboardButton("اضافه کردن پاسخ گزارش", callback_data="BTN:add_report_response")
    BTN_EDIT_REPORT_QUICK_RESPONSE = InlineKeyboardButton("ویرایش پاسخ گزارش", callback_data="BTN:edit_report_response")
    BTN_REMOVE_REPORT_QUICK_RESPONSE = InlineKeyboardButton("حذف پاسخ گزارش", callback_data="BTN:remove_report_response")

    BTN_EDIT_SUBJECTS = InlineKeyboardButton("ویرایش موضوعات", callback_data="BTN:EDIT_SUBJECTS")
    BTN_EDIT_SUBJECTS_EDIT = InlineKeyboardButton("ویرایش موضوع", callback_data="BTN:EDIT_SUBJECTS_EDIT")
    BTN_EDIT_SUBJECTS_ADD = InlineKeyboardButton("افزودن موضوع", callback_data="BTN:EDIT_SUBJECTS_ADD")
    BTN_EDIT_SUBJECTS_REMOVE = InlineKeyboardButton("حذف موضوع", callback_data="BTN:EDIT_SUBJECTS_REMOVE")

    BTN_EDIT_DEFINED_TEXT = InlineKeyboardButton("ویرایش متن آماده", callback_data="BTN:EDIT_DEFINED_TEXT")
    BTN_DEFINED_TEXT_ADD = InlineKeyboardButton("افزودن متن آماده", callback_data="BTN:DEFINED_TEXT_ADD")
    BTN_DEFINED_TEXT_EDIT = InlineKeyboardButton("ویرایش متن آماده", callback_data="BTN:DEFINED_TEXT_EDIT")
    BTN_DEFINED_TEXT_REMOVE = InlineKeyboardButton("حذف متن آماده", callback_data="BTN:DEFINED_TEXT_REMOVE")

    BTN_SETTING = InlineKeyboardButton("تنظیمات", callback_data="BTN:SETTING")
    BTN_SETTING_CRITICISM_ENABLE = InlineKeyboardButton("فعال/غیرفعال انتقاد", callback_data="BTN:SETTING_CRITICISM_ENABLE")
    BTN_SETTING_CRITICISM_ANONYMOUS = InlineKeyboardButton("انتقاد ناشناس", callback_data="BTN:SETTING_CRITICISM_ANONYMOUS")
    BTN_SETTING_CRITICISM_TEXT = InlineKeyboardButton("متن موضوع انتقاد", callback_data="BTN:SETTING_CRITICISM_TEXT")
    BTN_SETTING_TARGET_COMMAND = InlineKeyboardButton("دستور تعیین گروه", callback_data="BTN:SETTING_TARGET_COMMAND")
    BTN_SETTING_ACTIVE_CHAT_EXPIRATION = InlineKeyboardButton("عمر گفتگوی فعال", callback_data="BTN:SETTING_ACTIVE_CHAT_EXPIRATION")
    BTN_SETTING_CHAT_LIFE_SPAN = InlineKeyboardButton("مدت پاسخ‌گویی", callback_data="BTN:SETTING_CHAT_LIFE_SPAN")
    BTN_SETTING_ADMIN_PASSWORD = InlineKeyboardButton("رمز ادمین", callback_data="BTN:SETTING_ADMIN_PASSWORD")
    BTN_SETTING_ADMIN_BAN_DURATION = InlineKeyboardButton("محدودیت رمز اشتباه", callback_data="BTN:SETTING_ADMIN_BAN_DURATION")
    BTN_CHAT_HISTORY = InlineKeyboardButton("فایل‌های Chat History", callback_data="BTN:CHAT_HISTORY")
    
    BTN_EXIT = InlineKeyboardButton("خروج از پنل مدیریت", callback_data="BTN:EXIT")

    def __init__(self, bot:BotHandler):
        self._bot = bot
        self._messages = Messages()
        self._preferences = Preferences()
        # {chat_id: {"active": bool, "page": str, "field": str|None}}
        self._sessions = {}

    def _get_session(self, chat_id: str):
        if chat_id not in self._sessions:
            self._sessions[chat_id] = {
                "active": False,
                "page": self.PAGE_MAIN,
                "field": None,
            }
        return self._sessions[chat_id]

    def _set_page(self, chat_id: str, page: str):
        self._get_session(chat_id)["page"] = page

    def _get_page(self, chat_id: str):
        return self._get_session(chat_id)["page"]

    def _set_field(self, chat_id: str, field):
        self._get_session(chat_id)["field"] = field

    def _get_field(self, chat_id: str):
        return self._get_session(chat_id)["field"]

    def _set_active(self, chat_id: str, active: bool):
        self._get_session(chat_id)["active"] = active

    def _make_btn(self, text: str):
        return f"{self.BTN_PREFIX}{text}"

    def _parse_btn(self, data: str):
        if data.startswith(self.BTN_PREFIX):
            return data.removeprefix(self.BTN_PREFIX)
        return None

    def _make_defined_subject_callback(self, subject:str):
        return self._make_btn(f"DEFINED_SUBJECT:{subject}")

    def _parse_defined_subject_callback(self, data:str):
        payload = self._parse_btn(data)
        prefix = "DEFINED_SUBJECT:"
        if payload and payload.startswith(prefix):
            return payload.removeprefix(prefix)
        return None

    def _make_defined_text_item_callback(self, index:int):
        return self._make_btn(f"DEFINED_ITEM:{index}")

    def _parse_defined_text_item_callback(self, data:str):
        payload = self._parse_btn(data)
        prefix = "DEFINED_ITEM:"
        if payload and payload.startswith(prefix):
            try:
                return int(payload.removeprefix(prefix))
            except:
                return None
        return None

    def _make_history_file_callback(self, index:int):
        return self._make_btn(f"HISTORY_FILE:{index}")

    def _parse_history_file_callback(self, data:str):
        payload = self._parse_btn(data)
        prefix = "HISTORY_FILE:"
        if payload and payload.startswith(prefix):
            try:
                return int(payload.removeprefix(prefix))
            except:
                return None
        return None

    def isActive(self, chat_id: str):
        return self._get_session(chat_id)["active"]
    
    async def mainPage(self, chat_id:str):
        self._set_active(chat_id, True)
        self._set_page(chat_id, self.PAGE_MAIN)
        self._set_field(chat_id, None)
        menu = InlineKeyboardMarkup()
        menu.add(self.BTN_EDIT_MESSAGES, row=1)
        menu.add(self.BTN_EDIT_QUICK_RESPONSE, row=2)
        menu.add(self.BTN_EDIT_SUBJECTS, row=3)
        menu.add(self.BTN_EDIT_DEFINED_TEXT, row=4) 
        menu.add(self.BTN_SETTING, row=5)
        menu.add(self.BTN_CHAT_HISTORY, row=6)
        menu.add(self.BTN_EXIT, row=7)
        await self._bot.sendTemporaryMessage(chat_id, "شما به عنوان مدیر وارد شدید. گزینه‌های زیر در اختیار شماست:", components=menu)

    async def messageMenu(self, chat_id:str):
        self._set_page(chat_id, self.PAGE_MESSAGES)
        self._set_field(chat_id, None)
        messages = self._messages.getAllMessages()
        menu = InlineKeyboardMarkup()
        text = "پیام‌های موجود به این صورت است:\n"
        for item in messages.items():
            text+=f"{item[0]}:\n{item[1]}\n"
        text+="درصورت تمایل می‌توانید گزینهٔ مورد نظر را برای تغییر انتخاب کرده و یا به منو اصلی بازگردید."
        row = 1
        for item in messages:
            menu.add(InlineKeyboardButton(item, callback_data=self._make_btn(item)), row=row)
            row+=1
        menu.add(self.BTN_MAIN_MENU, row=row)
        await self._bot.sendTemporaryMessage(chat_id, text,components=menu)
        
    async def exit(self, chat_id:str):
        self._set_active(chat_id, False)
        self._set_page(chat_id, self.PAGE_MAIN)
        self._set_field(chat_id, None)
        menu = Menu()
        await self._bot.sendTemporaryMessage(chat_id, "شما از پنل مدیریت خارج شدید.",components=menu.start_only())

    async def askNewMessageText(self, chat_id:str, key:str, old_value:str):
        menu = InlineKeyboardMarkup()
        menu.add(self.BTN_RETURN, row=1)
        menu.add(self.BTN_MAIN_MENU, row=2)
        self._set_page(chat_id, self.PAGE_ASK_FOR_MESSAGE)
        self._set_field(chat_id, key)
        await self._bot.sendTemporaryMessage(chat_id, f"متن فعلی:\n{old_value}\nلطفاً متن جدید را بفرستید و یا اینکه از دکمهٔ زیر جهت بازگشت به منو قبلی استفاده کنید.", components=menu)
    
    async def getNewMessageText(self, chat_id:str, text:str):
        field = self._get_field(chat_id)
        if not field:
            await self.messageMenu(chat_id)
            return
        self._messages.set(field, text)
        self._set_field(chat_id, None)
        await self._bot.send_message(chat_id, "متن جدید ذخیره شد")
    
    async def quickResponseMenu(self, chat_id:str):
        self._set_page(chat_id, self.PAGE_QUICK_RESPONSE)
        self._set_field(chat_id, None)
        menu = InlineKeyboardMarkup()
        menu.add(self.BTN_ADD_CRITICISM_QUICK_RESPONSE, 1)
        menu.add(self.BTN_EDIT_CRITICISM_QUICK_RESPONSE,2)
        menu.add(self.BTN_REMOVE_CRITICISM_QUICK_RESPONSE,3)
        menu.add(self.BTN_ADD_REPORT_QUICK_RESPONSE, 4)
        menu.add(self.BTN_EDIT_REPORT_QUICK_RESPONSE, 5)
        menu.add(self.BTN_REMOVE_REPORT_QUICK_RESPONSE, 6)
        menu.add(self.BTN_MAIN_MENU,7)
        await self._bot.sendTemporaryMessage(chat_id, "لطفاً یکی از گزینه‌های زیر را انتخاب کنید.", components=menu)

    async def quickResponseSubMenu(self, chat_id:str, data:str):
        menu = InlineKeyboardMarkup()
        
        text_add = "لطفاً متن مورد نظر را ارسال کنید و یا یکی از گزینه‌های زیر را انتخاب کنید."
        text_edit = "لطفاً پیام مورد نظر را انتخاب نموده و یا به منو قبل برگردید."

        qr = QuickResponses()
        qrl = []

        aux = 1
        if data == self.BTN_ADD_CRITICISM_QUICK_RESPONSE.callback_data:
            self._set_page(chat_id, self.PAGE_ADD_CRITICISM_QUICK_RESPONSE)
            text = text_add
        elif data == self.BTN_EDIT_CRITICISM_QUICK_RESPONSE.callback_data:
            self._set_page(chat_id, self.PAGE_EDIT_CRITICISM_QUICK_RESPONSE)
            text = text_edit
            qrl = qr.getCriticismQuickResponse()
        elif data == self.BTN_REMOVE_CRITICISM_QUICK_RESPONSE.callback_data:
            self._set_page(chat_id, self.PAGE_REMOVE_CRITICISM_QUICK_RESPONSE)
            text = text_edit
            qrl = qr.getCriticismQuickResponse()
        elif data == self.BTN_ADD_REPORT_QUICK_RESPONSE.callback_data:
            self._set_page(chat_id, self.PAGE_ADD_REPORT_QUICK_RESPONSE)
            text = text_add
        elif data == self.BTN_EDIT_REPORT_QUICK_RESPONSE.callback_data:
            self._set_page(chat_id, self.PAGE_EDIT_REPORT_QUICK_RESPONSE)
            text = text_edit
            qrl = qr.getReportQuickResponses()
        elif data == self.BTN_REMOVE_REPORT_QUICK_RESPONSE.callback_data:
            self._set_page(chat_id, self.PAGE_REMOVE_REPORT_QUICK_RESPONSE)
            text = text_edit
            qrl = qr.getReportQuickResponses()
        
        for item in qrl:
            menu.add(InlineKeyboardButton(item, callback_data=self._make_btn(item)), aux)
            aux+=1
        menu.add(self.BTN_RETURN, aux)
        menu.add(self.BTN_MAIN_MENU, aux+1)
        await self._bot.sendTemporaryMessage(chat_id, text, components=menu)

    async def addQuickResponce(self, chat_id:str, text:str):
        await self._bot.send_message(chat_id, "گزینهٔ مورد نظر اضافه شد.")
        qr = QuickResponses()
        page = self._get_page(chat_id)
        if page == self.PAGE_ADD_CRITICISM_QUICK_RESPONSE:
            qr.addCriticismQuickResponse(text)
        elif page == self.PAGE_ADD_REPORT_QUICK_RESPONSE:
            qr.addReportQuickResponse(text)
        await self.quickResponseMenu(chat_id)
    
    async def quickResponseGetItem(self, chat_id:str, btn:str):
        text = self._parse_btn(btn)
        if text is None:
            await self.quickResponseMenu(chat_id)
            return
        qr = QuickResponses()
        menu = InlineKeyboardMarkup()
        menu.add(self.BTN_RETURN)
        menu.add(self.BTN_MAIN_MENU, row=2)
        page = self._get_page(chat_id)
        if page == self.PAGE_EDIT_CRITICISM_QUICK_RESPONSE:
            index = qr.getCriticismQuickResponse().index(text)+1
            self._set_field(chat_id, str(index))
            await self._bot.sendTemporaryMessage(chat_id, f"متن فعلی:\n{text}\nمتن جدید را وارد نمایید و یا از دکمه‌های زیر استفاده کنید.", components=menu)
        elif page == self.PAGE_EDIT_REPORT_QUICK_RESPONSE:
            index = qr.getReportQuickResponses().index(text)+1
            self._set_field(chat_id, str(index))
            await self._bot.sendTemporaryMessage(chat_id, f"متن فعلی:\n{text}\nمتن جدید را وارد نمایید و یا از دکمه‌های زیر استفاده کنید.", components=menu)
        elif page == self.PAGE_REMOVE_CRITICISM_QUICK_RESPONSE:
            await self._bot.send_message(chat_id, f"گزینهٔ «{text}» حذف شد.")
            index = qr.getCriticismQuickResponse().index(text)+1
            qr.removeCriticismQuickResponse(str(index))
            await self.quickResponseMenu(chat_id)
        elif page == self.PAGE_REMOVE_REPORT_QUICK_RESPONSE:
            await self._bot.send_message(chat_id, f"گزینهٔ «{text}» حذف شد.")
            index = qr.getReportQuickResponses().index(text)+1
            qr.removeReportQuickResponse(str(index))
            await self.quickResponseMenu(chat_id)
    
    async def quickResponseUpdateItem(self, chat_id:str, text:str):
        qr = QuickResponses()
        page = self._get_page(chat_id)
        field = self._get_field(chat_id)
        if not field:
            await self.quickResponseMenu(chat_id)
            return
        if page == self.PAGE_EDIT_CRITICISM_QUICK_RESPONSE:
            qr.setCriticismQuickResponse(field,text)            
        elif page == self.PAGE_EDIT_REPORT_QUICK_RESPONSE:
            qr.setReportQuickResponse(field,text)
        await self._bot.send_message(chat_id, "متن جدید ذخیره شد.")
        self._set_field(chat_id, None)
        await self.quickResponseMenu(chat_id)
    
    async def editSubjectsMenu(self, chat_id:str):
        self._set_page(chat_id, self.PAGE_EDIT_SUBJECTS)
        self._set_field(chat_id, None)
        menu = InlineKeyboardMarkup()
        menu.add(self.BTN_EDIT_SUBJECTS_ADD, 1)
        menu.add(self.BTN_EDIT_SUBJECTS_EDIT, 2)
        menu.add(self.BTN_EDIT_SUBJECTS_REMOVE, 3)
        menu.add(self.BTN_MAIN_MENU, 4)
        await self._bot.sendTemporaryMessage(chat_id, "لطفاً گزینهٔ مورد نظر را انتخاب کنید", menu)

    async def askSubject(self, chat_id:str):
        self._set_page(chat_id, self.PAGE_ADD_SUBJECT)
        menu = InlineKeyboardMarkup()
        menu.add(self.BTN_RETURN, 1)
        menu.add(self.BTN_MAIN_MENU, 2)
        await self._bot.sendTemporaryMessage(chat_id, "لطفاً موضوع مورد نظر را وارد کنید.\n\
                                              در صورت تمایل به تعیین مکان قرار گرفتن از '@' \
                                             بعد از متن مورد نظر استفاده کنید. مثلا:\n subject@2", menu)
    
    async def addSubject(self, chat_id:str, text:str):
        text = text.split("@")
        try:
            index = int(text[1])
        except:
            index = None
        text = text[0]
        subjects = Subjects()
        subjects.addSubject(text, index)
        await self._bot.send_message(chat_id, f"{text} اضافه شد")
        await self.mainPage(chat_id)

    async def selectSubject(self, chat_id:str, btn:str):
        act = ""        
        if btn == self.BTN_EDIT_SUBJECTS_EDIT.callback_data:
            self._set_page(chat_id, self.PAGE_EDIT_SUBJECT)
            act = "ویرایش"
        elif btn == self. BTN_EDIT_SUBJECTS_REMOVE.callback_data:
            self._set_page(chat_id, self.PAGE_REMOVE_SUBJECT)
            act = "حذف"
        
        subjects = list(Subjects())
        
        menu = InlineKeyboardMarkup()

        row = 1
        for subject in subjects:
            menu.add(InlineKeyboardButton(subject, callback_data=self._make_btn(subject)),row)
            row+=1
        menu.add(self.BTN_RETURN,row)
        row+=1
        menu.add(self.BTN_MAIN_MENU,row)        
        await self._bot.sendTemporaryMessage(chat_id, f"لطفاً گزینهٔ مورد نظر را برای {act} انتخاب کنید", menu)

    async def subjectGetItem(self, chat_id:str, btn:str):
        text = self._parse_btn(btn)
        if text is None:
            await self.editSubjectsMenu(chat_id)
            return
        subject = Subjects()
        menu = InlineKeyboardMarkup()
        menu.add(self.BTN_RETURN)
        menu.add(self.BTN_MAIN_MENU, row=2)
        page = self._get_page(chat_id)
        if page == self.PAGE_EDIT_SUBJECT:            
            self._set_field(chat_id, text)
            await self._bot.sendTemporaryMessage(chat_id, f"متن فعلی:\n{text}\nمتن جدید را وارد نمایید و یا از دکمه‌های زیر استفاده کنید.", components=menu)
        elif page == self.PAGE_REMOVE_SUBJECT:
            subject.removeSubject(text)
            await self._bot.send_message(chat_id, f"گزینهٔ «{text}» حذف شد.")
            await self.mainPage(chat_id)
        
    async def subjectUpdate(self, chat_id:str, data:str):
        field = self._get_field(chat_id)
        if not field:
            await self.editSubjectsMenu(chat_id)
            return
        subject = Subjects()
        subject.editSubjects(field, data)
        self._set_field(chat_id, None)
        await self._bot.send_message(chat_id, "موضوع بروزرسانی شد")
        await self.mainPage(chat_id)

    async def definedTextSelectSubjectMenu(self, chat_id:str):
        self._set_page(chat_id, self.PAGE_DEFINED_TEXT_SUBJECT)
        self._set_field(chat_id, None)
        subjects = list(Subjects())

        menu = InlineKeyboardMarkup()
        row = 1
        for subject in subjects:
            menu.add(InlineKeyboardButton(subject, callback_data=self._make_defined_subject_callback(subject)), row)
            row+=1
        menu.add(self.BTN_RETURN, row)
        row+=1
        menu.add(self.BTN_MAIN_MENU, row)
        await self._bot.sendTemporaryMessage(chat_id, "موضوع مورد نظر را برای مدیریت متن‌های آماده انتخاب کنید.", components=menu)

    async def definedTextActionMenu(self, chat_id:str, subject:str):
        self._set_page(chat_id, self.PAGE_DEFINED_TEXT_ACTION)
        self._set_field(chat_id, {"subject":subject})
        texts = Subjects().getDefinedTexts(subject)

        menu = InlineKeyboardMarkup()
        menu.add(self.BTN_DEFINED_TEXT_ADD, row=1)
        menu.add(self.BTN_DEFINED_TEXT_EDIT, row=2)
        menu.add(self.BTN_DEFINED_TEXT_REMOVE, row=3)
        menu.add(self.BTN_RETURN, row=4)
        menu.add(self.BTN_MAIN_MENU, row=5)
        await self._bot.sendTemporaryMessage(chat_id,
            f"موضوع: {subject}\nتعداد متن آماده: {len(texts)}\nلطفاً عملیات مورد نظر را انتخاب کنید.",
            components=menu)

    async def askDefinedTextToAdd(self, chat_id:str):
        self._set_page(chat_id, self.PAGE_DEFINED_TEXT_ADD)
        menu = InlineKeyboardMarkup()
        menu.add(self.BTN_RETURN, row=1)
        menu.add(self.BTN_MAIN_MENU, row=2)
        await self._bot.sendTemporaryMessage(chat_id, "متن آماده جدید را ارسال کنید.", components=menu)

    async def addDefinedText(self, chat_id:str, text:str):
        field = self._get_field(chat_id) or {}
        subject = field.get("subject")
        if not subject:
            await self.definedTextSelectSubjectMenu(chat_id)
            return
        added = Subjects().addDefinedText(subject, text)
        if added:
            await self._bot.send_message(chat_id, "متن آماده اضافه شد.")
        else:
            await self._bot.send_message(chat_id, "افزودن متن آماده انجام نشد.")
        await self.definedTextActionMenu(chat_id, subject)

    async def definedTextSelectItemMenu(self, chat_id:str, action:str):
        # action: edit/remove
        field = self._get_field(chat_id) or {}
        subject = field.get("subject")
        if not subject:
            await self.definedTextSelectSubjectMenu(chat_id)
            return
        texts = Subjects().getDefinedTexts(subject)

        if action == "edit":
            self._set_page(chat_id, self.PAGE_DEFINED_TEXT_EDIT_SELECT)
            title = f"موضوع: {subject}\nمتن آماده مورد نظر برای ویرایش را انتخاب کنید."
        else:
            self._set_page(chat_id, self.PAGE_DEFINED_TEXT_REMOVE_SELECT)
            title = f"موضوع: {subject}\nمتن آماده مورد نظر برای حذف را انتخاب کنید."

        menu = InlineKeyboardMarkup()
        row = 1
        for i, item in enumerate(texts, start=1):
            preview = item if len(item) < 40 else item[:37]+"..."
            menu.add(InlineKeyboardButton(f"{i}) {preview}", callback_data=self._make_defined_text_item_callback(i)), row=row)
            row+=1
        menu.add(self.BTN_RETURN, row)
        row+=1
        menu.add(self.BTN_MAIN_MENU, row)
        if not texts:
            title += "\nدر حال حاضر متن آماده‌ای برای این موضوع ثبت نشده است."
        await self._bot.sendTemporaryMessage(chat_id, title, components=menu)

    async def askDefinedTextToEdit(self, chat_id:str, index:int):
        field = self._get_field(chat_id) or {}
        subject = field.get("subject")
        if not subject:
            await self.definedTextSelectSubjectMenu(chat_id)
            return
        texts = Subjects().getDefinedTexts(subject)
        if index < 1 or index > len(texts):
            await self.definedTextSelectItemMenu(chat_id, "edit")
            return
        self._set_page(chat_id, self.PAGE_DEFINED_TEXT_EDIT_INPUT)
        self._set_field(chat_id, {"subject":subject, "index":index})

        menu = InlineKeyboardMarkup()
        menu.add(self.BTN_RETURN, row=1)
        menu.add(self.BTN_MAIN_MENU, row=2)
        await self._bot.sendTemporaryMessage(chat_id,
            f"متن فعلی:\n{texts[index-1]}\n\nمتن جدید را ارسال کنید.",
            components=menu)

    async def updateDefinedText(self, chat_id:str, text:str):
        field = self._get_field(chat_id) or {}
        subject = field.get("subject")
        index = field.get("index")
        if not subject or not index:
            await self.definedTextSelectSubjectMenu(chat_id)
            return
        edited = Subjects().editDefinedText(subject, int(index), text)
        if edited:
            await self._bot.send_message(chat_id, "متن آماده بروزرسانی شد.")
        else:
            await self._bot.send_message(chat_id, "بروزرسانی متن آماده انجام نشد.")
        await self.definedTextActionMenu(chat_id, subject)

    async def removeDefinedText(self, chat_id:str, index:int):
        field = self._get_field(chat_id) or {}
        subject = field.get("subject")
        if not subject:
            await self.definedTextSelectSubjectMenu(chat_id)
            return
        removed = Subjects().removeDefinedText(subject, index)
        if removed:
            await self._bot.send_message(chat_id, "متن آماده حذف شد.")
        else:
            await self._bot.send_message(chat_id, "حذف متن آماده انجام نشد.")
        await self.definedTextActionMenu(chat_id, subject)

    async def settingsMenu(self, chat_id:str):
        """Show current settings and available edit actions."""
        self._set_page(chat_id, self.PAGE_SETTINGS)
        self._set_field(chat_id, None)

        enabled = "فعال" if self._preferences.isCriticismEnabled() else "غیرفعال"
        anonymous = "فعال" if self._preferences.isCriticismAnonymous() else "غیرفعال"
        criticism_text = self._preferences.getCriticismText()
        target_cmd = self._preferences.getSetTargetCommand()
        active_exp = self._preferences.getActiveChatExpiration()
        life_span = self._preferences.getChatLifeSpan()
        admin_password = self._preferences.getAdminPassword()
        admin_ban_hours = self._preferences.getAdminRequestBanDuration()

        text = (
            "تنظیمات فعلی:\n"
            f"انتقاد: {enabled}\n"
            f"انتقاد ناشناس: {anonymous}\n"
            f"متن موضوع انتقاد: {criticism_text}\n"
            f"دستور تعیین گروه: {target_cmd}\n"
            f"عمر گفتگوی فعال (ساعت): {active_exp}\n"
            f"مدت پاسخ‌گویی (ساعت): {life_span}\n"
            f"رمز ادمین: {admin_password}\n"
            f"مدت محدودیت رمز اشتباه (ساعت): {admin_ban_hours}\n\n"
            "گزینه مورد نظر را انتخاب کنید."
        )

        menu = InlineKeyboardMarkup()
        menu.add(self.BTN_SETTING_CRITICISM_ENABLE, row=1)
        menu.add(self.BTN_SETTING_CRITICISM_ANONYMOUS, row=2)
        menu.add(self.BTN_SETTING_CRITICISM_TEXT, row=3)
        menu.add(self.BTN_SETTING_TARGET_COMMAND, row=4)
        menu.add(self.BTN_SETTING_ACTIVE_CHAT_EXPIRATION, row=5)
        menu.add(self.BTN_SETTING_CHAT_LIFE_SPAN, row=6)
        menu.add(self.BTN_SETTING_ADMIN_PASSWORD, row=7)
        menu.add(self.BTN_SETTING_ADMIN_BAN_DURATION, row=8)
        menu.add(self.BTN_RETURN, row=9)
        menu.add(self.BTN_MAIN_MENU, row=10)
        await self._bot.sendTemporaryMessage(chat_id, text, components=menu)

    async def askSettingValue(self, chat_id:str, setting_key:str, prompt:str):
        """Ask for a new value for a text/number setting."""
        self._set_page(chat_id, self.PAGE_SETTING_INPUT)
        self._set_field(chat_id, setting_key)
        menu = InlineKeyboardMarkup()
        menu.add(self.BTN_RETURN, row=1)
        menu.add(self.BTN_MAIN_MENU, row=2)
        await self._bot.sendTemporaryMessage(chat_id, prompt, components=menu)

    async def updateSettingValue(self, chat_id:str, data:str):
        setting_key = self._get_field(chat_id)
        if not setting_key:
            await self.settingsMenu(chat_id)
            return

        value = data.strip()

        if setting_key == "criticism_text":
            if not value:
                await self._bot.send_message(chat_id, "متن نمی‌تواند خالی باشد.")
                return
            self._preferences.setCriticismText(value)
        elif setting_key == "target_command":
            if not value:
                await self._bot.send_message(chat_id, "دستور نمی‌تواند خالی باشد.")
                return
            self._preferences.setSetTargetCommand(value)
        elif setting_key == "active_chat_expiration":
            if not value.isdigit() or int(value) < 1:
                await self._bot.send_message(chat_id, "عدد معتبر وارد کنید (بزرگ‌تر از صفر).")
                return
            self._preferences.setActiveChatExpiration(value)
        elif setting_key == "chat_life_span":
            if not value.isdigit() or int(value) < 1:
                await self._bot.send_message(chat_id, "عدد معتبر وارد کنید (بزرگ‌تر از صفر).")
                return
            self._preferences.setChatLifeSpan(value)
        elif setting_key == "admin_password":
            if not value:
                await self._bot.send_message(chat_id, "رمز عبور نمی‌تواند خالی باشد.")
                return
            self._preferences.setAdminPassword(value)
        elif setting_key == "admin_request_ban_hours":
            if not value.isdigit() or int(value) < 1:
                await self._bot.send_message(chat_id, "عدد معتبر وارد کنید (بزرگ‌تر از صفر).")
                return
            self._preferences.setAdminRequestBanDuration(value)
        else:
            await self.settingsMenu(chat_id)
            return

        self._set_field(chat_id, None)
        await self._bot.send_message(chat_id, "تنظیمات بروزرسانی شد.")
        await self.settingsMenu(chat_id)

    async def chatHistoryMenu(self, chat_id:str):
        """List files inside Chat History and allow admin to view file entries."""
        self._set_page(chat_id, self.PAGE_CHAT_HISTORY)
        history_dir = BASE_DIR / "Chat History"

        if not history_dir.exists() or not history_dir.is_dir():
            menu = InlineKeyboardMarkup()
            menu.add(self.BTN_RETURN, row=1)
            menu.add(self.BTN_MAIN_MENU, row=2)
            self._set_field(chat_id, {"files": []})
            await self._bot.sendTemporaryMessage(chat_id, "پوشهٔ Chat History یافت نشد.", components=menu)
            return

        files = sorted(
            [p for p in history_dir.iterdir() if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        self._set_field(chat_id, {"files": [p.name for p in files]})

        menu = InlineKeyboardMarkup()
        row = 1
        for i, file_path in enumerate(files, start=1):
            label = file_path.name
            if len(label) > 40:
                label = label[:37] + "..."
            menu.add(InlineKeyboardButton(label, callback_data=self._make_history_file_callback(i)), row=row)
            row += 1
        menu.add(self.BTN_RETURN, row=row)
        row += 1
        menu.add(self.BTN_MAIN_MENU, row=row)

        if files:
            text = "یکی از فایل‌های Chat History را انتخاب کنید تا موارد آن نمایش داده شود."
        else:
            text = "هیچ فایلی در پوشهٔ Chat History وجود ندارد."
        await self._bot.sendTemporaryMessage(chat_id, text, components=menu)

    def _split_history_entries(self, content:str):
        """
        Split DictionaryLogger logs using line separator "----------".
        Returns non-empty entries.
        """
        entries = []
        current = []
        for line in content.splitlines():
            if line.strip() == "----------":
                entry = "\n".join(current).strip()
                if entry:
                    entries.append(entry)
                current = []
                continue
            current.append(line)

        entry = "\n".join(current).strip()
        if entry:
            entries.append(entry)
        return entries

    def _chunk_text(self, text:str, limit:int=3500):
        if len(text) <= limit:
            return [text]
        chunks = []
        current = ""
        for line in text.splitlines(True):
            if len(current) + len(line) > limit:
                if current:
                    chunks.append(current)
                    current = ""
                if len(line) > limit:
                    for i in range(0, len(line), limit):
                        chunks.append(line[i:i+limit])
                else:
                    current = line
            else:
                current += line
        if current:
            chunks.append(current)
        return chunks

    async def sendHistoryEntries(self, chat_id:str, index:int):
        field = self._get_field(chat_id) or {}
        names = field.get("files", [])
        if index < 1 or index > len(names):
            await self.chatHistoryMenu(chat_id)
            return

        selected_name = names[index - 1]
        history_dir = (BASE_DIR / "Chat History").resolve()
        file_path = (history_dir / selected_name).resolve()

        # Prevent path traversal and invalid selection.
        if history_dir not in file_path.parents or not file_path.is_file():
            await self._bot.send_message(chat_id, "فایل انتخاب‌شده معتبر نیست.")
            await self.chatHistoryMenu(chat_id)
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except:
            await self._bot.send_message(chat_id, "خواندن فایل با خطا مواجه شد.")
            return

        entries = self._split_history_entries(content)
        if not entries:
            await self._bot.send_message(chat_id, f"فایل «{selected_name}» موردی برای نمایش ندارد.")
            return

        await self._bot.send_message(chat_id, f"فایل «{selected_name}» شامل {len(entries)} مورد است.")
        await asyncio.sleep(1)
        for i, entry in enumerate(entries, start=1):
            header = f"مورد {i} از {len(entries)}:\n"
            chunks = self._chunk_text(entry, limit=3400)
            if chunks:
                # send first chunk with entry index header
                await self._bot.send_message(chat_id, header + chunks[0])
                await asyncio.sleep(1)
                for part in chunks[1:]:
                    await self._bot.send_message(chat_id, part)
                    await asyncio.sleep(1)

    async def handle(self, chat_id:str, data:str):
        page = self._get_page(chat_id)

        # Main menu routing
        if page == self.PAGE_MAIN:
            if data == self.BTN_EDIT_MESSAGES.callback_data:
                await self.messageMenu(chat_id)
            elif data == self.BTN_EDIT_QUICK_RESPONSE.callback_data:
                await self.quickResponseMenu(chat_id)
            elif data == self.BTN_EDIT_SUBJECTS.callback_data:
                await self.editSubjectsMenu(chat_id)
            elif data == self.BTN_EDIT_DEFINED_TEXT.callback_data:
                await self.definedTextSelectSubjectMenu(chat_id)
            elif data == self.BTN_SETTING.callback_data:
                await self.settingsMenu(chat_id)
            elif data == self.BTN_CHAT_HISTORY.callback_data:
                await self.chatHistoryMenu(chat_id)
            elif data == self.BTN_EXIT.callback_data:
                await self.exit(chat_id)                    

        # Message templates management
        elif page == self.PAGE_MESSAGES:
            messages = self._messages.getAllMessages()
            btn = self._parse_btn(data) or ""
            if btn in messages:
                await self.askNewMessageText(chat_id, btn, messages[btn])
            elif data == self.BTN_MAIN_MENU.callback_data:
                await self.mainPage(chat_id)
            else:
                # none of buttons? ask again.
                await self.messageMenu(chat_id)

        elif page == self.PAGE_ASK_FOR_MESSAGE:
            if data == self.BTN_RETURN.callback_data:
                # return to messages menu
                await self.messageMenu(chat_id)
            elif data == self.BTN_MAIN_MENU.callback_data:
                await self.mainPage(chat_id)
            else:
                await self.getNewMessageText(chat_id, data)
                await self.messageMenu(chat_id)

        # Quick response management
        elif page == self.PAGE_QUICK_RESPONSE:
            if data == self.BTN_MAIN_MENU.callback_data:
                await self.mainPage(chat_id)
            elif data in [
                self.BTN_ADD_CRITICISM_QUICK_RESPONSE.callback_data,
                self.BTN_EDIT_CRITICISM_QUICK_RESPONSE.callback_data,
                self.BTN_REMOVE_CRITICISM_QUICK_RESPONSE.callback_data,
                self.BTN_ADD_REPORT_QUICK_RESPONSE.callback_data,
                self.BTN_EDIT_REPORT_QUICK_RESPONSE.callback_data,
                self.BTN_REMOVE_REPORT_QUICK_RESPONSE.callback_data
                ]:
                await self.quickResponseSubMenu(chat_id, data)
            else:
                await self.quickResponseMenu(chat_id)
        
        elif page in [            
            self.PAGE_EDIT_CRITICISM_QUICK_RESPONSE,
            self.PAGE_REMOVE_CRITICISM_QUICK_RESPONSE,
            self.PAGE_EDIT_REPORT_QUICK_RESPONSE,
            self.PAGE_REMOVE_REPORT_QUICK_RESPONSE
            ]:
            if data.startswith("BTN:"):
                # when user just click on list item
                if data == self.BTN_RETURN.callback_data:
                    await self.quickResponseMenu(chat_id)
                    return
                if data == self.BTN_MAIN_MENU.callback_data:
                    await self.mainPage(chat_id)
                    return
                await self.quickResponseGetItem(chat_id, data)
            else:
                if self._get_field(chat_id):
                    # when waiting for new data
                    await self.quickResponseUpdateItem(chat_id, data)
                else:
                    await self.quickResponseMenu(chat_id)
        elif page == self.PAGE_ADD_CRITICISM_QUICK_RESPONSE or page == self.PAGE_ADD_REPORT_QUICK_RESPONSE:
            if data == self.BTN_RETURN.callback_data:
                await self.quickResponseMenu(chat_id)
            elif data == self.BTN_MAIN_MENU.callback_data:
                await self.mainPage(chat_id)
            else: 
                await self.addQuickResponce(chat_id, data)

        # Subject management
        elif page == self.PAGE_EDIT_SUBJECTS:
            if data == self.BTN_EDIT_SUBJECTS_ADD.callback_data:
                await self.askSubject(chat_id)
            elif data== self.BTN_MAIN_MENU.callback_data:
                await self.mainPage(chat_id)
            elif data == self.BTN_EDIT_SUBJECTS_EDIT.callback_data or data == self.BTN_EDIT_SUBJECTS_REMOVE.callback_data:
                await self.selectSubject(chat_id, data)

        elif page == self.PAGE_ADD_SUBJECT:
            if data == self.BTN_MAIN_MENU.callback_data:
                await self.mainPage(chat_id)
            elif data == self.BTN_RETURN.callback_data:
                await self.editSubjectsMenu(chat_id)
            else:
                await self.addSubject(chat_id, data)

        elif page in [self.PAGE_EDIT_SUBJECT, self.PAGE_REMOVE_SUBJECT]:
            if data.startswith("BTN:"):                
                # when user just click on list item
                if data == self.BTN_MAIN_MENU.callback_data:
                    await self.mainPage(chat_id)
                    return
                elif data == self.BTN_RETURN.callback_data:
                    await self.editSubjectsMenu(chat_id)
                    return
                await self.subjectGetItem(chat_id, data)
            else:
                # when waiting for new data
                await self.subjectUpdate(chat_id, data)

        # Defined text management for subjects.ini
        elif page == self.PAGE_DEFINED_TEXT_SUBJECT:
            if data == self.BTN_MAIN_MENU.callback_data:
                await self.mainPage(chat_id)
            elif data == self.BTN_RETURN.callback_data:
                await self.mainPage(chat_id)
            else:
                subject = self._parse_defined_subject_callback(data)
                if subject and subject in Subjects():
                    await self.definedTextActionMenu(chat_id, subject)
                else:
                    await self.definedTextSelectSubjectMenu(chat_id)

        elif page == self.PAGE_DEFINED_TEXT_ACTION:
            field = self._get_field(chat_id) or {}
            subject = field.get("subject")
            if data == self.BTN_MAIN_MENU.callback_data:
                await self.mainPage(chat_id)
            elif data == self.BTN_RETURN.callback_data:
                await self.definedTextSelectSubjectMenu(chat_id)
            elif data == self.BTN_DEFINED_TEXT_ADD.callback_data:
                await self.askDefinedTextToAdd(chat_id)
            elif data == self.BTN_DEFINED_TEXT_EDIT.callback_data:
                await self.definedTextSelectItemMenu(chat_id, "edit")
            elif data == self.BTN_DEFINED_TEXT_REMOVE.callback_data:
                await self.definedTextSelectItemMenu(chat_id, "remove")
            elif subject:
                await self.definedTextActionMenu(chat_id, subject)
            else:
                await self.definedTextSelectSubjectMenu(chat_id)

        elif page == self.PAGE_DEFINED_TEXT_ADD:
            field = self._get_field(chat_id) or {}
            subject = field.get("subject")
            if data == self.BTN_MAIN_MENU.callback_data:
                await self.mainPage(chat_id)
            elif data == self.BTN_RETURN.callback_data:
                if subject:
                    await self.definedTextActionMenu(chat_id, subject)
                else:
                    await self.definedTextSelectSubjectMenu(chat_id)
            else:
                await self.addDefinedText(chat_id, data)

        elif page == self.PAGE_DEFINED_TEXT_EDIT_SELECT:
            field = self._get_field(chat_id) or {}
            subject = field.get("subject")
            if data == self.BTN_MAIN_MENU.callback_data:
                await self.mainPage(chat_id)
            elif data == self.BTN_RETURN.callback_data:
                if subject:
                    await self.definedTextActionMenu(chat_id, subject)
                else:
                    await self.definedTextSelectSubjectMenu(chat_id)
            else:
                index = self._parse_defined_text_item_callback(data)
                if index is None:
                    await self.definedTextSelectItemMenu(chat_id, "edit")
                else:
                    await self.askDefinedTextToEdit(chat_id, index)

        elif page == self.PAGE_DEFINED_TEXT_EDIT_INPUT:
            field = self._get_field(chat_id) or {}
            subject = field.get("subject")
            if data == self.BTN_MAIN_MENU.callback_data:
                await self.mainPage(chat_id)
            elif data == self.BTN_RETURN.callback_data:
                if subject:
                    await self.definedTextSelectItemMenu(chat_id, "edit")
                else:
                    await self.definedTextSelectSubjectMenu(chat_id)
            else:
                await self.updateDefinedText(chat_id, data)

        elif page == self.PAGE_DEFINED_TEXT_REMOVE_SELECT:
            field = self._get_field(chat_id) or {}
            subject = field.get("subject")
            if data == self.BTN_MAIN_MENU.callback_data:
                await self.mainPage(chat_id)
            elif data == self.BTN_RETURN.callback_data:
                if subject:
                    await self.definedTextActionMenu(chat_id, subject)
                else:
                    await self.definedTextSelectSubjectMenu(chat_id)
            else:
                index = self._parse_defined_text_item_callback(data)
                if index is None:
                    await self.definedTextSelectItemMenu(chat_id, "remove")
                else:
                    await self.removeDefinedText(chat_id, index)

        elif page == self.PAGE_SETTINGS:
            if data == self.BTN_MAIN_MENU.callback_data:
                await self.mainPage(chat_id)
            elif data == self.BTN_RETURN.callback_data:
                await self.mainPage(chat_id)
            elif data == self.BTN_SETTING_CRITICISM_ENABLE.callback_data:
                self._preferences.setCriticismEnabled(not self._preferences.isCriticismEnabled())
                await self.settingsMenu(chat_id)
            elif data == self.BTN_SETTING_CRITICISM_ANONYMOUS.callback_data:
                self._preferences.setCriticismAnonymous(not self._preferences.isCriticismAnonymous())
                await self.settingsMenu(chat_id)
            elif data == self.BTN_SETTING_CRITICISM_TEXT.callback_data:
                await self.askSettingValue(chat_id, "criticism_text", "متن جدید موضوع انتقاد را ارسال کنید.")
            elif data == self.BTN_SETTING_TARGET_COMMAND.callback_data:
                await self.askSettingValue(chat_id, "target_command", "دستور جدید تعیین گروه مقصد را ارسال کنید.")
            elif data == self.BTN_SETTING_ACTIVE_CHAT_EXPIRATION.callback_data:
                await self.askSettingValue(chat_id, "active_chat_expiration", "عمر گفتگوی فعال (ساعت) را به صورت عدد وارد کنید.")
            elif data == self.BTN_SETTING_CHAT_LIFE_SPAN.callback_data:
                await self.askSettingValue(chat_id, "chat_life_span", "مدت پاسخ‌گویی (ساعت) را به صورت عدد وارد کنید.")
            elif data == self.BTN_SETTING_ADMIN_PASSWORD.callback_data:
                await self.askSettingValue(chat_id, "admin_password", "رمز جدید ادمین را ارسال کنید.")
            elif data == self.BTN_SETTING_ADMIN_BAN_DURATION.callback_data:
                await self.askSettingValue(chat_id, "admin_request_ban_hours", "مدت محدودیت (ساعت) را به صورت عدد وارد کنید.")
            else:
                await self.settingsMenu(chat_id)

        elif page == self.PAGE_SETTING_INPUT:
            if data == self.BTN_MAIN_MENU.callback_data:
                await self.mainPage(chat_id)
            elif data == self.BTN_RETURN.callback_data:
                await self.settingsMenu(chat_id)
            else:
                await self.updateSettingValue(chat_id, data)

        elif page == self.PAGE_CHAT_HISTORY:
            if data == self.BTN_MAIN_MENU.callback_data:
                await self.mainPage(chat_id)
            elif data == self.BTN_RETURN.callback_data:
                await self.mainPage(chat_id)
            else:
                index = self._parse_history_file_callback(data)
                if index is None:
                    await self.chatHistoryMenu(chat_id)
                else:
                    await self.sendHistoryEntries(chat_id, index)
