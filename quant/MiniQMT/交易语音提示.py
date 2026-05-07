import pyttsx3

# 初始化语音引擎
engine = pyttsx3.init()

# 设置语速（rate范围一般在50-200之间）
rate = engine.getProperty('rate')
engine.setProperty('rate', 150)  # 150 words per minute

# 设置音量（volume范围0.0-1.0）
volume = engine.getProperty('volume')
engine.setProperty('volume', 0.9)

# 可选：设置语音（如果有多个语音包）
voices = engine.getProperty('voices')
# 切换为中文语音（索引可能因系统而异，需自行测试）
# engine.setProperty('voice', voices[0].id)  # 英文语音
# engine.setProperty('voice', voices[1].id)  # 中文语音（需系统安装中文语音包）

# 朗读文本
text = "000001.SZ已经触发买入信号。"
engine.say(text)

# 等待朗读完成
engine.runAndWait()

# 保存朗读内容为音频文件（部分系统支持）
# engine.save_to_file(text, 'output.mp3')
# engine.runAndWait()



'''
import pygame
import time

# 初始化pygame音频模块
pygame.mixer.init()

# 加载并播放音频文件（支持MP3、WAV等）
pygame.mixer.music.load("audio.mp3")  # 替换为你的音频文件路径
pygame.mixer.music.play()

# 等待播放完成（根据音频时长调整）
time.sleep(5)  # 播放5秒后停止
pygame.mixer.music.stop()
'''