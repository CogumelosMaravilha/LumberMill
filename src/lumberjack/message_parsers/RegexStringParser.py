import sys
import re
import BaseModule

class RegexStringParser(BaseModule.BaseModule):
    
    def configure(self, configuration):
        self.message_types = []
        self.fieldextraction_regexpressions = {}
        self.success_marker = self.failure_marker = False
        for message_type, regex_pattern in configuration['field_extraction_patterns'].items():
            self.message_types.append(message_type)
            try:
                regex = re.compile(regex_pattern)
            except Exception, e:
                self.logger.error("RegEx error for pattern %s. Exception: %s, Error: %s" % (regex_pattern, Exception, e))
                sys.exit(255)
            self.fieldextraction_regexpressions[message_type] = regex
        if 'mark-on-success' in configuration:
            self.success_marker = configuration['mark-on-success']
        if 'mark-on-failure' in configuration:
            self.failure_marker = configuration['mark-on-failure']            

    def handleData(self, data):
        """
        This method expects a syslog datagram.
        It might contain more then one message. We split at the newline char.
        """
        self.logger.debug("Received raw message: %s" % data)
        message = data['data']
        # Remove possible remaining syslog error code
        # i.e. message starts with <141>
        try:
            if message.index(">") <= 4:
                message = message[message.index(">")+1:] + "\n"
        except: 
            pass
        if message.strip() == "":
            return
        data['data'] = message
        return self.parseMessage(data)
        
    def parseMessage(self, data):
        """
        When a message type was successfully detected, extract the fields with to corresponding regex pattern
        """
        matches = False
        message = data['data']
        self.logger.debug("Input to parseMessage: %s" % message)
        for message_type, regex in self.fieldextraction_regexpressions.iteritems():
            matches = regex.search(message);
            if matches:
                data.update(matches.groupdict())
                data.update({'message_type': message_type})
                if self.success_marker:
                    data['markers'].append(self.success_marker)
                break
        if not matches:
            if self.failure_marker:
                data['markers'].append(self.failure_marker)            
            self.logger.debug("Could not extract fields for message %s." % message);
            data.update({'message_type': 'unknown'})
        self.logger.debug("Output from parseMessage %s" % data)
        return data
            