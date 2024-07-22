from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from moviepy.editor import VideoFileClip, concatenate_videoclips
# from google.cloud import speech_v1p1beta1 as speech
# from google.cloud import texttospeech
import os
import tempfile
from google.cloud import speech, texttospeech, translate_v2 as translate
from moviepy.editor import *
import sys
import requests

app = FastAPI()

# Google Cloud credentials file path
GOOGLE_APPLICATION_CREDENTIALS = "gcp-key.json"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gcp-key.json"

def video2audio(video_file_path):
    # Convert video file to audio file
    video_clip = VideoFileClip(video_file_path)
    audio_clip = video_clip.audio
#     audio_filename = tempfile.mktemp(".flac")
    audio_filename = video_file_path.split('.')[0]+".flac"
    print(audio_filename)
    audio_clip.write_audiofile(audio_filename, codec="flac")
    return audio_filename
    

def speach2text(audio_filename, transcription_language_code):
    # Initialize client for speech recognition
    client = speech.SpeechClient()
    transcriptions = []

    with open(audio_filename, "rb") as audio_file:
        audio_content = audio_file.read()

    audio = speech.RecognitionAudio(content=audio_content)
    print(audio)
    config = speech.RecognitionConfig(
                                        encoding=speech.RecognitionConfig.AudioEncoding.FLAC,
                                        sample_rate_hertz=44100,
                                        language_code=transcription_language_code,
                                        audio_channel_count=2,
                                        enable_automatic_punctuation=True
                                    )

    try:
        response = client.recognize(config=config, audio=audio)
        for result in response.results:
            transcription = result.alternatives[0].transcript
            transcriptions.append(transcription)
    except Exception as e:
        print(f"Transcription error: {e}")

    full_transcription = ' '.join(transcriptions)
    
    return full_transcription


def text2speach(translation, translation_language_code, selected_voice):
    try:
        text_to_speech_client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=translation)#['translatedText'])
        voice = texttospeech.VoiceSelectionParams(
                                                language_code=translation_language_code,
                                                name=selected_voice
                                                )
        audio_config = texttospeech.AudioConfig(
                                                audio_encoding=texttospeech.AudioEncoding.MP3
                                                )

        response = text_to_speech_client.synthesize_speech(
                                                            input=synthesis_input,
                                                            voice=voice,
                                                            audio_config=audio_config
                                                        )

        temp_audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        print(temp_audio_file)
        temp_audio_file.write(response.audio_content)
        temp_audio_file.close()
    except Exception as e:
        print(f"Text to Speach error: {e}")
        
        

    def speach2video(video_file_path, temp_audio_file):
        try:
            # Determine new video filename
            original_dir, original_filename = os.path.split(video_file_path)
            name_part, extension_part = os.path.splitext(original_filename)
            new_filename = f"{name_part}_translated{extension_part}"
            final_video_path = os.path.join(original_dir, new_filename)

            # Create new video with translated audio
            final_video_clip = video_clip.set_audio(AudioFileClip(temp_audio_file.name))
            final_video_clip.write_videofile(final_video_path, codec="libx264", audio_codec="aac")

            print(f"Translated video created: {final_video_path}")
        except Exception as e:
            print(f"Translation error: {e}")



# Initialize Google Cloud Speech-to-Text and Text-to-Speech clients
speech_to_text_client = speech.SpeechClient.from_service_account_file(GOOGLE_APPLICATION_CREDENTIALS)
text_to_speech_client = texttospeech.TextToSpeechClient.from_service_account_file(GOOGLE_APPLICATION_CREDENTIALS)


def text_translate(source_lang: str, target_lang: str, text: str):
# text_translate(full_transcription, translation_language_code):
    # try:
    translate_client = translate.Client()
    translation = translate_client.translate(values= text,
                                            target_language=target_lang,
                                            source_language=source_lang
                                            )
    # except Exception as e:
    #     print(f"Translation error: {e}")
    
    return translation


# @app.get("/")
# def root():
#     return {"Hello" : "World"}


@app.get("/translate")
async def translate_text(source_lang: str, target_lang: str, text: str):
    """
    Translate text from source language to target language.
    :param source_lang: Source language code (e.g., 'en' for English)
    :param target_lang: Target language code (e.g., 'fr' for French)
    :param text: Text to be translated
    :return: Translated text
    """
    # Check if source and target languages are provided
    if not source_lang or not target_lang:
        raise HTTPException(status_code=400, detail="Source and target languages are required")

    # Check if text is provided
    if not text:
        raise HTTPException(status_code=400, detail="Text to be translated is required")

    # Translation request payload
    payload = {
        "q": text,
        "source": source_lang,
        "target": target_lang,
        "format": "text"
    }

    # Translation request headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GOOGLE_APPLICATION_CREDENTIALS}"
    }


    # Make translation request to the Translation API
    # text_translate(source_lang: str, target_lang: str, text: str)
    # TRANSLATION_API_URL = "https://translation.googleapis.com/language/translate/v2"

    # response = requests.post(TRANSLATION_API_URL, json=payload, headers=headers)
    response = text_translate(source_lang=source_lang, target_lang=target_lang, text=text)
    print(response)
    # # Check if request was successful
    # if response.status_code != 200:
    #     raise HTTPException(status_code=response.status_code, detail="Translation request failed")


    # # Parse translation response
    # translation = response.json().get("data", {}).get("translations", [{}])[0].get("translatedText", "")

    # return {"translation": translation}
    return {"translation":response['translatedText']}




@app.post("/audio_translate/")
async def translate_audio(source_lang: str, target_lang: str, audio_file: UploadFile = File(...)):
    """
    Translate audio message from source language to target language.
    :param source_lang: Source language code (e.g., 'en' for English)
    :param target_lang: Target language code (e.g., 'fr' for French)
    :param audio_file: Audio file containing the message to be translated
    :return: Translated audio file
    """
    # Check if source and target languages are provided
    if not source_lang or not target_lang:
        raise HTTPException(status_code=400, detail="Source and target languages are required")

    # Read audio file content
    audio_content = await audio_file.read()

    orig_audio_file = "uploaded_audio.wav"
    with open(orig_audio_file, "wb") as f:
        f.write(audio_content)


    client = speech.SpeechClient()
    # Perform speech-to-text transcription
    audio_content = open(orig_audio_file, "rb").read()

    audio = speech.RecognitionAudio(content=audio_content)
   
    audio_config = speech.RecognitionConfig(
                                        encoding=speech.RecognitionConfig.AudioEncoding.FLAC,
                                        sample_rate_hertz=44100,
                                        language_code=source_lang,
                                        audio_channel_count=2,
                                        enable_automatic_punctuation=True
                                    )

    # response = speech_to_text_client.recognize(request={"config": audio_config, "audio": audio})
    response = client.recognize(config=audio_config, audio=audio)

    # Extract transcribed text
    transcript = ""
    for result in response.results:
        transcript += result.alternatives[0].transcript

    # Perform translation of transcribed text
    # translation_response = translate_text(transcript, target_lang)
    response_tranlate = text_translate(source_lang=source_lang, target_lang=target_lang, text=transcript)
    translation_response=response_tranlate['translatedText']

    print("translation_response", translation_response)

    # Synthesize translated text into audio
    synthesis_input = texttospeech.SynthesisInput(text=translation_response)
    voice_params = texttospeech.VoiceSelectionParams(language_code=target_lang, ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)

    response = text_to_speech_client.synthesize_speech(input=synthesis_input, voice=voice_params, audio_config=audio_config)

    # Write translated audio to a file
    translated_audio_path = "translated_audio.wav"
    with open(translated_audio_path, "wb") as f:
        f.write(response.audio_content)



    # client = speech.SpeechClient()
    # transcriptions = []

    # audio = speech.RecognitionAudio(content=audio_content)
    # # print(audio)
    # config = speech.RecognitionConfig(
    #                                     # encoding=speech.RecognitionConfig.AudioEncoding.FLAC,
    #                                     sample_rate_hertz=44100,
    #                                     language_code=source_lang,
    #                                     audio_channel_count=2,
    #                                     # enable_automatic_punctuation=True
    #                                 )
    # # try:
    # # response = client.recognize(config=config, audio=audio)
    # response = speech_to_text_client.recognize(request={"config": audio_config, "audio": audio})
    # print("RESULTSSSSSS \n", response.results)
    # # Extract transcribed text
    # transcript = ""
    # for result in response.results:
    #     transcript += result.alternatives[0].transcript
    # # except Exception as e:
    # #     print(f"Transcription error: {e}")

    # print("="*50)
    # print(transcript)
    # print("="*50)

    # # Perform translation of transcribed text
    # response_tranlate = text_translate(source_lang=source_lang, target_lang=target_lang, text=transcript)
    # translation_response=response_tranlate['translatedText']

    # # Synthesize translated text into audio
    # synthesis_input = texttospeech.SynthesisInput(text=translation_response)
    # voice_params = texttospeech.VoiceSelectionParams(language_code=target_lang, ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL)
    # audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)

    # response = text_to_speech_client.synthesize_speech(input=synthesis_input, voice=voice_params, audio_config=audio_config)

    # # Write translated audio to a file
    # translated_audio_file = "translated_audio.wav"
    # with open(translated_audio_file, "wb") as f:
    #     f.write(response.audio_content)


    return FileResponse(path=translated_audio_path, filename="translated_audio.wav")




@app.post("/translate_video/")
async def translate_video(source_lang: str, target_lang: str, selected_voice: str, video_file: UploadFile = File(...)):
    """
    Translate video from source language to target language.
    :param source_lang: Source language code (e.g., 'en' for English)
    :param target_lang: Target language code (e.g., 'fr' for French)
    :param selected_voice: Selected voice for translation voice over
    :param video_file: Video file containing the message to be translated
    :return: Translated video file
    """
    # Check if source and target languages are provided
    if not source_lang or not target_lang:
        raise HTTPException(status_code=400, detail="Source and target languages are required")

    # Save the uploaded video file
    video_path = "uploaded_video.mp4"
    with open(video_path, "wb") as f:
        f.write(await video_file.read())

    # Extract audio from the video
    video_clip = VideoFileClip(video_path)
    audio_path = "extracted_audio.wav"
    video_clip.audio.write_audiofile(audio_path)
    video_clip.close()

    # Perform speech-to-text transcription
    audio_content = open(audio_path, "rb").read()
    audio = speech.RecognitionAudio(content=audio_content)

    audio_config = speech.RecognitionConfig(
                                        # encoding=speech.RecognitionConfig.AudioEncoding.FLAC,
                                        sample_rate_hertz=44100,
                                        language_code=source_lang,
                                        audio_channel_count=2,
                                        # enable_automatic_punctuation=True
                                    )

    response = speech_to_text_client.recognize(request={"config": audio_config, "audio": audio})

    # Extract transcribed text
    transcript = ""
    for result in response.results:
        transcript += result.alternatives[0].transcript

    # Perform translation of transcribed text
    # translation_response = translate_text(transcript, target_lang)
    response_tranlate = text_translate(source_lang=source_lang, target_lang=target_lang, text=transcript)
    translation_response=response_tranlate['translatedText']

    # Synthesize translated text into audio
    synthesis_input = texttospeech.SynthesisInput(text=translation_response)
    voice_params = texttospeech.VoiceSelectionParams(language_code=target_lang, ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)

    response = text_to_speech_client.synthesize_speech(input=synthesis_input, voice=voice_params, audio_config=audio_config)

    # Write translated audio to a file
    translated_audio_path = "translated_audio.wav"
    with open(translated_audio_path, "wb") as f:
        f.write(response.audio_content)

    # Merge translated audio with original video
    translated_audio_clip = AudioFileClip(translated_audio_path)
    video_clip = VideoFileClip(video_path)
    video_clip_with_audio = video_clip.set_audio(translated_audio_clip)

    # Save the translated video file
    translated_video_path = "translated_video.mp4"
    video_clip_with_audio.write_videofile(translated_video_path)

    # Delete temporary files
    os.remove(video_path)
    os.remove(audio_path)
    os.remove(translated_audio_path)

    return FileResponse(path=translated_video_path, filename="translated_video.mp4")


