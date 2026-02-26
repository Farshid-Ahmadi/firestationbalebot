from configparser import ConfigParser

class Target:
    """Backward-compatible wrapper around Preferences target settings."""
    def __init__(self):
        self.preferences = Preferences()

    def get(self)->str:
        """returns str or None if target is not saved"""
        return self.preferences.getTarget()

    def set(self,target:str):
        """save target"""
        self.preferences.setTarget(target)

class Messages:
    WELCOME = "welcome"
    CANCEL = "cancel"
    CLIENT_TAG = "client_tag"
    ASK_CONTACT = "ask_contact" 
    CRITICISM_TAG = "criticism_text_tag" 
    ASK_TEXT = "ask_text" 
    INCIDENT_TAG = "incident_text_tag" 
    ASK_INCIDENT_DESCRIPTION = "ask_incident_description"
    RECEIVED_DATA_TAG = "received_data_tag"
    ASK_APPROVE = "ask_approve"
    CONFIRMATION_OF_RECEIPT = "confirmation_of_receipt"
    ADDRESS_TAG = "address_tag"
    ASK_ADDRESS = "ask_address"
    INFO = "info"
    
    DEFAULT_MESSAGES = {
        WELCOME: "سلام. لطفاً موضوع گزارش را انتخاب کنید.",
        CANCEL: "گزارش شما لغو شد.",
        CLIENT_TAG: "اطلاعات تماس:",
        ASK_CONTACT: "لطفاً شماره تماس خود را ارسال کنید.",
        CRITICISM_TAG: "انتقاد و پیشنهاد:",
        ASK_TEXT: "لطفاً متن خود را وارد کنید.",
        INCIDENT_TAG: "گزارش حادثه:",
        ASK_INCIDENT_DESCRIPTION: "شرح حادثه را وارد کنید یا یکی از متن‌های آماده را انتخاب کنید.",
        RECEIVED_DATA_TAG: "اطلاعات دریافت‌شده:",
        ASK_APPROVE: "در صورت صحت اطلاعات، گزینهٔ تأیید را انتخاب کنید.",
        CONFIRMATION_OF_RECEIPT: "گزارش شما با موفقیت ثبت شد.",
        ADDRESS_TAG: "آدرس یا موقعیت مکانی:",
        ASK_ADDRESS: "لطفاً آدرس را بنویسید یا موقعیت مکانی را ارسال کنید.",
        INFO: "برای شروع گزارش جدید از دکمهٔ شروع مجدد استفاده کنید.",
    }

    def __init__(self):
        self.conf = ConfigParser()
        self.conf.read("messages.ini")

        update = False
        if "Messages" not in self.conf:
            self.conf["Messages"]={}
            update = True

        for key, default_value in self.DEFAULT_MESSAGES.items():
            if key not in self.conf["Messages"]:
                self.conf["Messages"][key] = default_value
                update = True

        if update:
            with open("messages.ini", "w") as file:
                self.conf.write(file)

    def getAllMessages(self):
        keys = list(self.DEFAULT_MESSAGES.keys())
        return {k:self.get(k) for k in keys}
    
    def get(self, key:str)->str:
        try:
            return self.conf["Messages"][key]
        except:
            return f"{key} Message Not Found!"
        
    def set(self, key:str, value:str):
        self.conf["Messages"][key] = value
        with open("messages.ini", "w") as file:
                self.conf.write(file)

class Preferences:
    def __init__(self):
        self.conf = ConfigParser()
        self.conf.read("setting.ini")

        # add section if section not found
        update = False
        if "Criticism" not in self.conf:
            default = {
                "enable" : True,
                "anonymous" : True,
                "text" : "📝 انتقاد و پیشنهاد"
            }
            self.conf["Criticism"]=default              # to prevent error create a new file
            update = True
             
        if "Report" not in self.conf:
            default = {
                "active_chat_expiration_hours" : "5",
                "can_reply_in_hours" : "48"
            }
            self.conf["Report"]=default              # to prevent error create a new file
            update = True
             
        if "System" not in self.conf:
            default = {
                "atkn": "Write your atkn here!",
                "admin": "0",
                "admin_password": "5454",
                "admin_request_ban_hours": "240",
            }
            self.conf["System"] = default               # to prevent error create a new file
            update = True
        else:
            if "admin" not in self.conf["System"]:
                self.conf["System"]["admin"] = "0"
                update = True
            if "admin_password" not in self.conf["System"]:
                self.conf["System"]["admin_password"] = "5454"
                update = True
            if "admin_request_ban_hours" not in self.conf["System"]:
                self.conf["System"]["admin_request_ban_hours"] = "240"
                update = True


        if "Target" not in self.conf:
            default = {
                "set_target_command" : 'ربات بفرست اینجا.',
                "target" : "None"
                }
            self.conf["Target"] = default               # to prevent error create a new file
            update = True
        else:
            if "target" not in self.conf["Target"]:
                self.conf["Target"]["target"] = "None"
                update = True
            if "set_target_command" not in self.conf["Target"]:
                self.conf["Target"]["set_target_command"] = 'ربات بفرست اینجا.'
                update = True

        if update:
            with open("setting.ini", "w") as file:
                self.conf.write(file)

    def _save(self):
        with open("setting.ini", "w") as file:
                self.conf.write(file)

    def _reload(self):
        self.conf.read("setting.ini")

    def isCriticismEnabled(self):
        self._reload()
        if "enable" not in self.conf["Criticism"]:
            raise KeyError("'enable' is not set in 'Criticism' section!")
        if self.conf["Criticism"]["enable"].capitalize() == "True":
            return True
        elif self.conf["Criticism"]["enable"].capitalize() == "False":
            return False
        else:
            raise ValueError("Critisism 'enable' not set properly!")

    def isCriticismAnonymous(self):
        self._reload()
        if "anonymous" not in self.conf["Criticism"]:
            raise KeyError("'anonymous' is not set in 'Criticism' section!")
        if self.conf["Criticism"]["anonymous"].capitalize() == "True":
            return True
        elif self.conf["Criticism"]["anonymous"].capitalize() == "False":
            return False
        else:
            raise ValueError("Critisism 'anonymous' not set properly!")
    
    def getCriticismText(self):
        self._reload()
        if "text" not in self.conf["Criticism"]:
            raise KeyError("'text' is not set in 'Criticism' section!")
        return self.conf["Criticism"]["text"]

    def setCriticismEnabled(self, enabled):
        self.conf["Criticism"]["enable"] = str(enabled)
        self._save()

    def setCriticismAnonymous(self, enabled):
        self.conf["Criticism"]["anonymous"] = str(enabled)
        self._save()
        
    def setCriticismText(self, text):
        self.conf["Criticism"]["text"] = str(text)
        self._save()

    def getApiToken(self):
        self._reload()
        if "atkn" not in self.conf["System"]:
            raise KeyError("'API TOKEN' is not set!")
        atkn = self.conf["System"]["atkn"]
        return atkn

    def getSetTargetCommand(self):
        self._reload()
        if "set_target_command" not in self.conf["Target"]:
            raise KeyError("'set_target_command' is not set!")
        return self.conf["Target"]["set_target_command"]

    def setSetTargetCommand(self, command):
        self.conf["Target"]["set_target_command"] = str(command)
        self._save()

    def getTarget(self):
        self._reload()
        target = self.conf["Target"].get("target", "None")
        if target == "None" or not target:
            return None
        return target

    def setTarget(self, target):
        if target is None:
            self.conf["Target"]["target"] = "None"
        else:
            self.conf["Target"]["target"] = str(target)
        self._save()

    def getActiveChatExpiration(self):
        self._reload()
        if "active_chat_expiration_hours" not in self.conf["Report"]:
            raise KeyError("active_chat_expiration_hours' is not set!")
        return self.conf["Report"]["active_chat_expiration_hours"]

    def setActiveChatExpiration(self, hours):
        self.conf["Report"]["active_chat_expiration_hours"] = str(hours)
        self._save()
    
    def getChatLifeSpan(self):
        self._reload()
        if "can_reply_in_hours" not in self.conf["Report"]:
            raise KeyError("'can_reply_in_hours' is not set!")
        return self.conf["Report"]["can_reply_in_hours"]

    def setChatLifeSpan(self, hours):
        self.conf["Report"]["can_reply_in_hours"] = str(hours)
        self._save()
    
    def getAdmin(self):
        self._reload()
        if "admin" not in self.conf["System"]:
            return "0"
        return self.conf["System"]["admin"]
    
    def setAdmin(self, chat_id):
        self.conf["System"]["admin"]=chat_id
        self._save()

    def getAdminPassword(self):
        self._reload()
        if "admin_password" not in self.conf["System"]:
            raise KeyError("'admin_password' is not set!")
        return self.conf["System"]["admin_password"]

    def setAdminPassword(self, password):
        self.conf["System"]["admin_password"] = str(password)
        self._save()

    def getAdminRequestBanDuration(self):
        self._reload()
        if "admin_request_ban_hours" not in self.conf["System"]:
            raise KeyError("'admin_request_ban_hours' is not set!")
        return self.conf["System"]["admin_request_ban_hours"]

    def setAdminRequestBanDuration(self, hours):
        self.conf["System"]["admin_request_ban_hours"] = str(hours)
        self._save()

class Subjects(dict):
    FILE = "subjects.ini"
    def __init__(self):
        self.conf = ConfigParser()
        self._checkFile()
        self._load()  

    def _checkFile(self):
        try:
            with open(self.FILE, "r") as file:        
                self.conf.read_file(file)
                if "Subjects" not in self.conf.sections():
                    self._createFile()
                    return
                for subject in self.conf["Subjects"].values():
                    if subject not in self.conf.sections():
                        self._createFile()
                        return
        except:
            self._createFile()

    def _createFile(self):
        data = {
            "Subjects":{
                "1" : "subject example 1",
                "2" : "subject example 2"
            },
            "subject example 1" :{
                "1" : "defined incident 1",
                "2" : "defined incident 2"
            },
            "subject example 2" :{
                "1" : "defined incident 1",
                "2" : "defined incident 2"
            }
        }
        conf = ConfigParser()
        conf.read_dict(data)
        with open(self.FILE,"w") as file:
            conf.write(file)

    def _load(self):
        self.clear()
        self.conf.read(self.FILE)

        # sorting subjects
        subject_sorting_keys = sorted(list(self.conf["Subjects"].keys()), key=lambda x: int(x))
        subjects = [self.conf["Subjects"][k] for k in subject_sorting_keys]

        for item in subjects:
            # sorting defined incidents
            data_sorting_keys = sorted(list(self.conf[item].keys()), key=lambda x: int(x))
            sorted_values = [self.conf[item][k] for k in data_sorting_keys]
            self[item]=sorted_values  

    def _isValidSubjectName(self, subject:str)->bool:
        return subject in self.conf.sections() and subject != "Subjects"

    def getDefinedTexts(self, subject:str)->list:
        """Return ordered predefined texts of a subject. Return [] if not found."""
        if not self._isValidSubjectName(subject):
            return []
        keys = sorted(list(self.conf[subject].keys()), key=lambda x: int(x))
        return [self.conf[subject][k] for k in keys]

    def addDefinedText(self, subject:str, text:str, index:int=None)->bool:
        """Add predefined text to subject. If index is None add to end."""
        if not self._isValidSubjectName(subject):
            return False
        if not text:
            return False

        number_of_items = len(self.conf[subject])
        if not index:
            index = number_of_items + 1
        elif index < 1:
            index = 1
        elif index > number_of_items + 1:
            index = number_of_items + 1

        # shift items to make room
        for i in range(number_of_items + 1, index, -1):
            self.conf[subject][str(i)] = self.conf[subject][str(i - 1)]
        self.conf[subject][str(index)] = text

        self._shiftToFillEmptyPlace(subject)
        self._save()
        return True

    def editDefinedText(self, subject:str, index:int, text:str)->bool:
        """Update predefined text by index (1-based)."""
        if not self._isValidSubjectName(subject):
            return False
        if not text:
            return False
        key = str(index)
        if key not in self.conf[subject]:
            return False
        self.conf[subject][key] = text
        self._save()
        return True

    def removeDefinedText(self, subject:str, index:int)->bool:
        """Remove predefined text by index (1-based)."""
        if not self._isValidSubjectName(subject):
            return False
        key = str(index)
        if key not in self.conf[subject]:
            return False
        self.conf[subject].pop(key)
        self._shiftToFillEmptyPlace(subject)
        self._save()
        return True

    def editSubjects(self, old:str, new:str):
        # check if there is old section or not
        if old not in self.conf.sections():
            return
        
        # new couldn't be Subjects
        if new == "Subjects":
            return
        
        subjects = list(self.conf["Subjects"])
        for i in subjects:
            if self.conf["Subjects"][i] == old:
                self.conf["Subjects"][i] = new
        
        self.conf.add_section(new)
        self.conf[new] = self.conf[old]
        self.conf.remove_section(old)
        self._save()
    
    def addSubject(self, text:str, index:int=None):
        # prevent repetitive subject
        if text in self:
            return
        
        # text couln't be Subjects
        if text == "Subjects":
            return
        
        number_of_items = len(self)

        # add to end if index is none
        if not index:
            index = number_of_items+1
        
        # shift others
        if index <= number_of_items:
            for i in range(number_of_items+1, index, -1):        
                self.conf["Subjects"][str(i)]=self.conf["Subjects"][str(i-1)]
        
        self.conf["Subjects"][str(index)]=text
        self.conf.add_section(text)

        self._shiftToFillEmptyPlace("Subjects")
        self._save()        

    def _save(self):
        with open(self.FILE,"w") as file:
            self.conf.write(file)
        self._load()

    def _shiftToFillEmptyPlace(self, section:str):
        keys = list(self.conf[section])
        
        # check if list is not empty sort it else return
        if not keys:
            return
        keys.sort(key=lambda x: int(x))

        resort = False

        if keys[0] != "1" :
            resort = True
        
        if len(keys)>1:
            for i in range(1, len(keys)):
                if int(keys[i])-int(keys[i-1]) != 1:
                    resort = True
        
        # resort if nessesary
        if resort:
            new_values = dict()
            for i in range(len(keys)):
                new_values[str(i+1)]=self.conf[section][keys[i]]
            
            self.conf[section] = new_values    

    def removeSubject(self, text:str):
        # return if not exists
        if text not in self:
            return      

        # protect Subjects
        if text == "Subjects":
            return

        for item in self.conf["Subjects"]:
            if self.conf["Subjects"][item] == text:
                self.conf["Subjects"].pop(item)
        self.conf.remove_section(text)

        self._shiftToFillEmptyPlace("Subjects")
        self._save()        
        
class QuickResponses:
    def __init__(self):
        super().__init__()
        self.conf = ConfigParser()
        self.conf.read("quick_responses.ini")

        # add section if section not found
        update = False
        if "Criticism" not in self.conf:            
            self.conf["Criticism"]={}              # to prevent error create a new file
            update = True
             
        if "Report" not in self.conf:        
            self.conf["Report"]={}              # to prevent error create a new file
            update = True
        if update:
            with open("quick_responses.ini", "w") as file:
                self.conf.write(file)
    def _getSorted(self, section):
        data = dict(self.conf[section].items())
        sorted_keys = sorted(list(self.conf[section].keys()))
        return [data[k] for k in sorted_keys]
    
    def getCriticismQuickResponse(self):
        return self._getSorted("Criticism")
    
    def getReportQuickResponses(self):
        return self._getSorted("Report")
    
    def setCriticismQuickResponse(self, index:str, text:str):
        self.conf["Criticism"][index] = text
        with open("quick_responses.ini", "w") as file:
                self.conf.write(file)

    def addCriticismQuickResponse(self, text:str):
        count = len(self.conf["Criticism"])
        self.setCriticismQuickResponse(str(count+1), text)
    
    def removeCriticismQuickResponse(self, index:str):
        self.conf["Criticism"].pop(index)
        with open("quick_responses.ini", "w") as file:
                self.conf.write(file)
    
    def setReportQuickResponse(self, index:str, text:str):
        self.conf["Report"][index] = text
        with open("quick_responses.ini", "w") as file:
                self.conf.write(file)
    
    def addReportQuickResponse(self, text:str):
        count = len(self.conf["Report"])
        self.setReportQuickResponse(str(count+1), text)
    
    def removeReportQuickResponse(self, index:str):
        self.conf["Report"].pop(index)
        with open("quick_responses.ini", "w") as file:
                self.conf.write(file)
        
if __name__=="__main__":
    # test
    # m = Subjects()
    # m.editSubjects("fdf","🚨 سایر حوادث")
    # m._load()
    # print(m)
    pass
