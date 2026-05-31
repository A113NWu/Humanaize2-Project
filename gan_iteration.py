from llm import chat
import re
import time, random, threading, requests


class GANIteration:
    def __init__(self):
        self.topic = ""
        self.reply_a = ""
        self.reply_b = ""
        self._if_stop = False
        self._stop_event = threading.Event()
        self._session = requests.Session()
        self.callback = None

    def _reset_session(self):
        try:
            if self._session:
                self._session.close()
        except Exception:
            pass
        self._session = requests.Session()
        self._stop_event.clear()
        self._if_stop = False

    def _check_stop(self):
        if self._if_stop or self._stop_event.is_set():
            return True
        return False

    def stop_immediately(self):
        self._if_stop = True
        self._stop_event.set()
        self.reply_b = "$Nothing$"
        try:
            if self._session:
                self._session.close()
        except Exception:
            pass

    def decide_use_gan(self, user_text, exec_instr, emotion_monitor=None):
        """
        Decide whether the assistant should perform GAN self-debate before answering.
        Returns:
            tuple(bool, str): whether to use GAN, and the decision explanation.
        """
        self._reset_session()
        if self._check_stop():
            return False, ""

        decision_prompt = (
            f"{exec_instr}\n\nUser question: {user_text}\n"
            "Should the assistant perform a GAN self-debate before answering this question? "
            "Answer with YES or NO and one short reason."
        )
        decision_reply = chat(decision_prompt, session=self._session, stop_event=self._stop_event)
        if not decision_reply:
            return False, ""
        decision_text = decision_reply.strip()
        match = re.search(r"\b(yes|no)\b", decision_text, re.I)
        if match:
            return match.group(1).lower() == "yes", decision_text
        return "yes" in decision_text.lower(), decision_text

    def self_debate(self, is_user_topic=False, user_topic=None):
        """
        GAN iteration: a self-debate between two perspectives.
        Args:
            is_user_topic (bool): whether the topic is defined by the user.
            user_topic (str): the user-provided topic if is_user_topic is True.
        Returns:
            dict: {"synthesis": str} with the final synthesis.
        """
        self._reset_session()
        if self._check_stop():
            return {"synthesis": ""}

        if is_user_topic:
            topic = user_topic
        else:
            topic = chat("Please generate a concise, academic debate topic, such as a reflection on humanity or an analysis of a social issue. The topic should be clear, brief, and strong.", session=self._session, stop_event=self._stop_event)
            if self._check_stop():
                return {"synthesis": ""}
            if self.callback:
                self.callback({"type": "gan_topic", "topic": topic})
            time.sleep(1)
        self.topic = topic

        if self._check_stop():
            return {"synthesis": ""}
        reply_a = chat("Please provide your argument on the following topic: %s" % topic, session=self._session, stop_event=self._stop_event)
        if self._check_stop():
            return {"synthesis": ""}
        self.reply_a = reply_a
        if self.callback:
            self.callback({"type": "gan_argument", "argument": reply_a})
        time.sleep(1)

        if self._check_stop():
            return {"synthesis": ""}
        reply_b = chat("For the topic '%s', do you find any issue with the following view: %s If yes, refute it logically. If not, reply with $Nothing$. Please do not output any text like $Nothing& when disagreeing." % (topic, reply_a), session=self._session, stop_event=self._stop_event)
        if self._check_stop():
            return {"synthesis": ""}
        self.reply_b = reply_b
        if self.callback:
            self.callback({"type": "gan_counter", "counter": reply_b})
        time.sleep(1)

        synthesis = reply_a
        while "$Nothing$" not in self.reply_b and not self._if_stop:
            if self._check_stop():
                return {"synthesis": ""}

            reply_a = chat("The user believes your view has this issue: %s. Please rebut it logically." % self.reply_b, session=self._session, stop_event=self._stop_event)
            if self._check_stop():
                return {"synthesis": ""}
            if self.callback:
                self.callback({"type": "gan_rebuttal", "rebuttal": reply_a})
            time.sleep(1)

            if self._check_stop():
                return {"synthesis": ""}
            reply_b = chat("For the topic '%s', do you find any issue with the following view: %s If yes, refute it logically. If not, reply with $Nothing$. Please do not output any text like $Nothing& when disagreeing." % (topic, reply_a), session=self._session, stop_event=self._stop_event)
            if self._check_stop():
                return {"synthesis": ""}
            self.reply_b = reply_b
            if self.callback:
                self.callback({"type": "gan_counter", "counter": reply_b})
            time.sleep(1)
            synthesis = reply_a

        if not self._if_stop:
            return {"synthesis": synthesis}
        return {"synthesis": ""}


if __name__ == "__main__":
    gan_iteration = GANIteration()
    result = gan_iteration.self_debate(True, "Please evaluate Donald Trump's political career.")
    print(result)