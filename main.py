from bale import Update, Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Location
from helper import DictionaryLogger, Menu, PasswordManager, ActiveChat, BotHandler, AdminView
from file_manager import Messages, Subjects, Preferences, QuickResponses
from database_handler import ChatHandler, AdminRequestBanningHandler 

if __name__ == "__main__":
    # Load subjects
    REPORT_SUBJECTS = Subjects()

    # Load Preferences
    preferences = Preferences()
    
    # Load messages
    messages = Messages()

    chat_handler = ChatHandler(preferences.getActiveChatExpiration(), preferences.getChatLifeSpan())     
    chat_logger = DictionaryLogger("Chat History")		# create a logger to save call details in log files
    menu = Menu()                                       # to create menu under messages easier
    bot = BotHandler(token=preferences.getApiToken())   # the bot which will be connected to bale

    admin_request_ban = AdminRequestBanningHandler(preferences.getAdminRequestBanDuration())
    pm=PasswordManager(preferences.getAdminPassword())
    pending_admin_login = set()
    admin_view = AdminView(bot)

    @bot.event
    async def on_ready():
        print(bot.user, "is Ready!")
        target_chat = preferences.getTarget()
        if target_chat:
            await bot.send_message(target_chat, f"{bot.user.username} is Ready!")

    @bot.event
    async def on_update(update: Update):
        if update.message:
            message: Message = update.message
            chat_id = str(message.chat_id)

            # keep runtime auth settings synchronized with admin panel changes
            pm.setPassword(preferences.getAdminPassword())
            admin_request_ban.setBanningDuration(preferences.getAdminRequestBanDuration())

            text = message.text.strip() if message.text else ""		# get command or text                        

            await bot.cleanUp(chat_id)          # clean what should be cleaned
            
            target_chat = preferences.getTarget()
            if target_chat and chat_id == target_chat:
                if (message.reply_to_message_id):
                    chat_and_message_ids = chat_handler.getChatAndMessageIds(message.reply_to_message_id)   #returns None if not saved
                    if chat_and_message_ids:
                        await bot.send_message(chat_and_message_ids[0], text,
                                               reply_to_message_id=chat_and_message_ids[1])
                        f_name = message.from_user.first_name+" " if message.from_user.first_name else ""
                        l_name = message.from_user.last_name+" " if message.from_user.last_name else ""
                        announce = f'{f_name}{l_name}به ایشان پاسخ داد:\n{text}'
                        await bot.send_message(target_chat, announce)  
                        return                

            else:
                # if it's not from target group

                if admin_view.isActive(chat_id):
                    # if it's in admin view
                    await admin_view.handle(chat_id, text)
                else:
                    # everything else!
                    active_chat:ActiveChat = chat_handler.getActiveChat(chat_id)   # current chat

                    if text == "/start" or text == menu.RESTART:
                        # get out of setting menu
                        pending_admin_login.discard(chat_id)
                        pm.reset(chat_id)

                        # create new chat
                        active_chat = ActiveChat(chat_id)
                        chat_handler.saveChat(active_chat)
                        
                        # add criticism to subjects if its enabled
                        if preferences.isCriticismEnabled():
                            REPORT_SUBJECTS.update({preferences.getCriticismText():None})
                        
                        #create subject inline keyboard
                        subjects_keyboard = InlineKeyboardMarkup()
                        row=1
                        for subject in REPORT_SUBJECTS:
                            subjects_keyboard.add(InlineKeyboardButton(subject, callback_data=subject), row=row)
                            row+=1
                        await bot.sendTemporaryMessage(chat_id, messages.get(messages.WELCOME), subjects_keyboard)    # send first message and ask for subject
                        return
                    
                    elif text == menu.CANCEL:
                        # get out of setting menu
                        pending_admin_login.discard(chat_id)
                        pm.reset(chat_id)

                        # cancel active chat            
                        active_chat.state = active_chat.States.CANCELLED
                        chat_logger.saveLog(active_chat.getDataInPersian())
                        chat_handler.saveChat(active_chat)
                        await bot.sendTemporaryMessage(chat_id, messages.get(messages.CANCEL), menu.start_only())    # send first message and ask for subject
                        return

                    elif chat_id in pending_admin_login:
                        # check password
                        pm_result = pm.check(chat_id, text)
                        if pm_result == "Granted":
                            await admin_view.mainPage(chat_id)
                            preferences.setAdmin(chat_id)
                            pending_admin_login.discard(chat_id)
                        elif pm_result == "Ban":
                            await bot.send_message(chat_id, "شما مسدود شدید و اجازه دسترسی به عنوان مدیر را نخواهید داشت. در صورت تمایل به ثبت پیام از دکمهٔ 'شروع مجدد' استفاده کنید.", components=menu.start_only())
                            admin_request_ban.ban(chat_id)
                            pending_admin_login.discard(chat_id)
                        elif pm_result == "Retry":
                            await bot.send_message(chat_id, "رمز وارد شده اشتباه بود. دومرتبه تلاش کنید.")
                        return

                    elif text == "ورود مدیریت" or text == "ورود مدیریت ":                    
                        if admin_request_ban.isBanned(chat_id):
                            return
                        if preferences.getAdmin() == chat_id:                        
                            await admin_view.mainPage(chat_id)
                            return
                        await bot.send_message(chat_id, "لطفاً رمز عبور را وارد کنید. در صورت سه مرتبه اشتباه کردن، مسدود خواهید شد.", components=menu.start_only())
                        pending_admin_login.add(chat_id)
                        return
                    
                    elif text == preferences.getSetTargetCommand():
                        preferences.setTarget(chat_id)
                        await bot.send_message(chat_id,"متوجه شدم!")
                        return                                    

                    if active_chat.state == active_chat.States.ADDRESS:
                        # save address or location
                        if message.location:
                            active_chat.longitute=message.location.longitude
                            active_chat.latitute=message.location.latitude
                        else:
                            active_chat.address=text
                        active_chat.state = active_chat.States.CONTACT
                        chat_handler.saveChat(active_chat)

                        # ask for contact
                        await bot.send_message(chat_id, messages.get(messages.CLIENT_TAG), components=menu.contact())
                        await bot.sendTemporaryMessage(chat_id, messages.get(messages.ASK_CONTACT))
                        return

                    elif active_chat.state == active_chat.States.CONTACT:
                        if message.contact:
                            # save contact
                            active_chat.phone=message.contact.phone_number
                            active_chat.name = f"{message.contact.first_name+' ' if message.contact.first_name else ''}{message.contact.last_name if message.contact.last_name else ''}"
                            active_chat.state = active_chat.States.MESSAGE
                            chat_handler.saveChat(active_chat)

                            if active_chat.subject == preferences.getCriticismText():
                                # if it's criticism ask for message
                                await bot.send_message(chat_id, messages.get(messages.CRITICISM_TAG), components=menu.start_cancel())
                                await bot.sendTemporaryMessage(chat_id, messages.get(messages.ASK_TEXT))

                            else:
                                # if its not criticism create suggesstion inline menu
                                suggested_messages = InlineKeyboardMarkup()
                                row = 1
                                for message in REPORT_SUBJECTS.get(active_chat.subject):
                                    suggested_messages.add(InlineKeyboardButton(message,callback_data=message),row=row)
                                    row+=1
                                
                                # ask for message
                                await bot.send_message(chat_id, messages.get(messages.INCIDENT_TAG), components=menu.start_cancel())
                                await bot.sendTemporaryMessage(chat_id, messages.get(messages.ASK_INCIDENT_DESCRIPTION),
                                                                    suggested_messages)
                        else:
                            await bot.sendTemporaryMessage(chat_id, messages.get(messages.ASK_CONTACT),components=menu.contact())
                        return

                    elif active_chat.state == active_chat.States.MESSAGE:
                        # save message
                        active_chat.message=text
                        active_chat.state = active_chat.States.APPROVE
                        chat_handler.saveChat(active_chat)
                        
                        # ask for approve
                        chat_data = f"{messages.get(messages.RECEIVED_DATA_TAG)} \n{active_chat}"
                        message_id = (await bot.send_message(chat_id, chat_data, components=menu.approve())).message_id
                        await bot.sendTemporaryMessage(chat_id, messages.get(messages.ASK_APPROVE))
                        # save message id to replay the result
                        chat_handler.saveClientMessageId(chat_id, message_id)
                        return

                    elif active_chat.state == active_chat.States.APPROVE:     
                        if text == menu.APPROVE:
                            await bot.send_message(chat_id, messages.get(messages.CONFIRMATION_OF_RECEIPT),
                                            components=menu.start_only())

                            # send to target
                            if not target_chat:
                                await bot.send_message(chat_id, "گروه مقصد هنوز تنظیم نشده است. لطفاً با دستور تعیین گروه، مقصد را مشخص کنید.")
                                return

                            response_menu = InlineKeyboardMarkup()
                            responses = QuickResponses()
                            if active_chat.subject == preferences.getCriticismText():
                                responses = responses.getCriticismQuickResponse()
                            else:
                                responses = responses.getReportQuickResponses()

                            row = 1
                            for item in responses:
                                response_menu.add(InlineKeyboardButton(item, callback_data=item),row=row)
                                row+=1

                            if active_chat.longitute and active_chat.latitute:  
                                header = f"{active_chat.subject} :\n تماس گیرنده {active_chat.name} با شماره تماس {active_chat.phone}\n موقعیت:"
                                await bot.send_message(target_chat,header)
                                await bot.send_location(target_chat,Location(active_chat.longitute, active_chat.latitute))
                                footer = f"شرح:\n{active_chat.message}\n\nشما می‌توانید به این درخواست پاسخ دهید و یا یکی از گزینه‌های زیر را انتخاب کنید:"                        
                                message_id = (await bot.send_message(target_chat,footer, components=response_menu)).message_id
                            else:
                                header = f"{active_chat.subject} :\n تماس گیرنده {active_chat.name} با شماره تماس {active_chat.phone}\n"
                                footer = f"شرح:\n{active_chat.message}\n"
                                if active_chat.address:
                                    footer += f"\nآدرس:\n{active_chat.address}\n"
                                body = header + footer + "\nشما می‌توانید به این درخواست پاسخ دهید و یا یکی از گزینه‌های زیر را انتخاب کنید:"
                                message_id = (await bot.send_message(target_chat, body, components=response_menu)).message_id
                            chat_handler.saveReportMessageId(chat_id, message_id)     # save message id to retrive client message id to tell her last response                    

                            # submit data
                            active_chat.state = active_chat.States.SUBMITTED
                            chat_handler.saveChat(active_chat)
                            chat_logger.saveLog(active_chat.getDataInPersian())
                        else:
                            await bot.sendTemporaryMessage(chat_id, messages.get(messages.ASK_APPROVE),components=menu.approve())
                        return
                    
                    await bot.sendTemporaryMessage(chat_id, messages.get(messages.INFO),menu.start_only())
                
    @bot.event
    async def on_callback(callback: CallbackQuery):
        data = callback.data
        chat_id = str(callback.message.chat_id)
                
        await bot.cleanUp(chat_id)                

        target_chat = preferences.getTarget()
        if target_chat and chat_id == target_chat:
            chat_and_message_ids = chat_handler.getChatAndMessageIds(callback.message.message_id)   #returns None if not saved
            if chat_and_message_ids:
                await bot.send_message(chat_and_message_ids[0], data,
                                        reply_to_message_id=chat_and_message_ids[1])                
                f_name = callback.from_user.first_name+" " if callback.from_user.first_name else ""
                l_name = callback.from_user.last_name+" " if callback.from_user.last_name else ""
                announce = f'{f_name}{l_name}به ایشان پاسخ داد:\n{data}'
                await bot.send_message(target_chat, announce)                
        else:   
            if admin_view.isActive(chat_id):
                # if it's in admin view
                await admin_view.handle(chat_id, data)
            else:
                # everything else!         
                active_chat:ActiveChat = chat_handler.getActiveChat(chat_id)

                if active_chat.state == active_chat.States.NEW:
                    # save subject
                    active_chat.subject = data        

                    await bot.send_message(chat_id, data+" :")  # send subject tag
                    
                    if data == preferences.getCriticismText():
                        # if its criticism
                        if preferences.isCriticismAnonymous():
                            # ask for message                    
                            active_chat.state = active_chat.States.MESSAGE
                            await bot.sendTemporaryMessage(chat_id, messages.get(messages.ASK_TEXT))
                        else:
                            # ask for contact
                            active_chat.state = active_chat.States.CONTACT
                            await bot.send_message(chat_id, messages.get(messages.CLIENT_TAG), components=menu.contact())
                            await bot.sendTemporaryMessage(chat_id, messages.get(messages.ASK_CONTACT))
                    else:
                        # ask for address
                        active_chat.state = active_chat.States.ADDRESS
                        await bot.send_message(chat_id, messages.get(messages.ADDRESS_TAG), components=menu.location())
                        await bot.sendTemporaryMessage(chat_id, messages.get(messages.ASK_ADDRESS))
                    
                    # save active chat in database
                    chat_handler.saveChat(active_chat)
                elif active_chat.state == active_chat.States.MESSAGE:            
                    # save message
                    active_chat.message = data            
                    active_chat.state = active_chat.States.APPROVE
                    chat_handler.saveChat(active_chat)

                    # ask for approve
                    chat_data = f"{messages.get(messages.RECEIVED_DATA_TAG)} \n{active_chat}"
                    message_id = (await bot.send_message(chat_id, chat_data, components=menu.approve())).message_id
                    chat_handler.saveClientMessageId(chat_id, message_id)
                    await bot.sendTemporaryMessage(chat_id, messages.get(messages.ASK_APPROVE))
                        
    bot.run()
