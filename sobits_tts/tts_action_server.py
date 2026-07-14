import rclpy
from rclpy.node import Node
import pygame
import time
import importlib
import io
import traceback
import os
from ament_index_python.packages import get_package_share_directory
from rclpy.executors import MultiThreadedExecutor

from sobits_interfaces.action import TextToSpeech as TextToSpeechAction
from sobits_interfaces.srv import TextToSpeech as TextToSpeechSrv
from rclpy.action import ActionServer, GoalResponse, CancelResponse

from sobits_tts.include._base_tts import BaseTTSModel

class TTSActionServer(Node):
    def __init__(self):
        super().__init__('tts_action_server')
        self.declare_parameter('tts_name', 'kokoro') 
        self.tts_name = self.get_parameter('tts_name').get_parameter_value().string_value
        self.get_logger().info(f"Selected TTS: {self.tts_name}")

        self.sample_rate = 24000 

        self._tts_model_instance = None
        self._mixer_initialized = False

        try:
            self.save_dir = os.path.join(get_package_share_directory('sobits_tts'), 'soundfile')
            self.output_filename = 'output.wav'
            self.output_filepath = os.path.join(self.save_dir, self.output_filename)

        except Exception as e:
            self.get_logger().fatal(f"Could not determine package source root directory: {e}")
            self.get_logger().fatal(traceback.format_exc())
            raise RuntimeError("Failed to determine package source path.")

        os.makedirs(self.save_dir, exist_ok=True)
        self.get_logger().info(f"Audio files will be saved to: {self.save_dir}")

        try:
            module_path = f'sobits_tts.include.{self.tts_name}_tts'
            tts_model_module = importlib.import_module(module_path)

            model_class_name = f"{self.tts_name.capitalize()}TTSModel"
            ModelClass = getattr(tts_model_module, model_class_name)

            if not issubclass(ModelClass, BaseTTSModel):
                raise TypeError(f"Model class {model_class_name} does not inherit from BaseTTSModel. Please check its definition.")

            self._tts_model_instance = ModelClass(node=self, sample_rate=self.sample_rate)
            self.get_logger().info(f"Successfully loaded and initialized TTS'{self.tts_name}'.")

        except Exception as e:
            self.get_logger().fatal(f"An error occurred during TTS loading/initialization for '{self.tts_name}': {e}")
            self.get_logger().fatal(traceback.format_exc())
            raise RuntimeError(f"Failed to load or initialize TTS '{self.tts_name}'.")

        try:
            pygame.mixer.init(frequency=self.sample_rate, size=-16, channels=1, buffer=512)
            self.get_logger().info("Pygame mixer initialized.")
            self._mixer_initialized = True
        except Exception as e:
            self.get_logger().error(f"Failed to initialize Pygame mixer: {e}. Audio playback may not work.")
            self._mixer_initialized = False

        self._action_server = ActionServer(
            self,
            TextToSpeechAction,
            'speech_word',
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback)
        self._speech_service = self.create_service(
            TextToSpeechSrv,
            'speech_word',
            self.service_callback)
        YELLOW = '\033[93m'
        ENDC = '\033[0m'
        self.get_logger().info(f"{YELLOW}TTS Action Server ready with: {self.tts_name}{ENDC}")
        self.get_logger().info(f"{YELLOW}TTS Service ready with: {self.tts_name}{ENDC}")

    def destroy_node(self):
        self.get_logger().info('Shutting down pygame...')
        if pygame.mixer.get_init():
            try:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
                self.get_logger().info('Pygame mixer quit.')
            except Exception as e:
                 self.get_logger().error(f"Error quitting Pygame mixer: {e}")
        super().destroy_node()

    def goal_callback(self, goal_request):
        self.get_logger().debug(f"Received goal request with text: '{goal_request.text}'")
        if not self._mixer_initialized or self._tts_model_instance is None:
            self.get_logger().error("Mixer or TTS not initialized. Rejecting goal.")
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def cancel_callback(self, goal_handle):
        self.get_logger().debug('Received cancel request.')
        return CancelResponse.ACCEPT

    def service_callback(self, request, response):
        success, total_time, _status = self._speak_text(request.text)
        response.success = success
        response.total_time = float(total_time)
        return response

    def execute_callback(self, goal_handle):
        feedback = TextToSpeechAction.Feedback()
        response = TextToSpeechAction.Result()
        text = goal_handle.request.text

        def should_cancel():
            return goal_handle.is_cancel_requested

        def publish_feedback(remaining_time, elapsed_time):
            response.total_time = float(elapsed_time)
            feedback.remaining_time = max(0.0, float(remaining_time))
            goal_handle.publish_feedback(feedback)

        success, total_time, status = self._speak_text(
            text,
            should_cancel=should_cancel,
            feedback_callback=publish_feedback)

        response.success = success
        response.total_time = float(total_time)

        if status == 'canceled':
            goal_handle.canceled()
        elif success:
            goal_handle.succeed()
        else:
            goal_handle.abort()

        return response

    def _speak_text(self, text, should_cancel=None, feedback_callback=None):
        if should_cancel is None:
            should_cancel = lambda: False

        if not isinstance(text, str) or not text.strip():
            self.get_logger().error(f"Input text is empty, blank, or not a string. Received: '{text}'")
            return False, 0.0, 'failed'

        self.get_logger().info(f"Processing text: [{text}] using {self.tts_name}.")

        if not pygame.mixer.get_init() or self._tts_model_instance is None:
            self.get_logger().error("Pygame mixer or TTS model is not initialized. Cannot play audio.")
            return False, 0.0, 'failed'

        play_time = 0.0
        audio_buffer = None

        try:
            if should_cancel():
                self.get_logger().info('Goal canceled before audio generation.')
                return False, 0.0, 'canceled'

            play_time, audio_buffer = self._tts_model_instance.generate_audio(text)

            if should_cancel():
                self.get_logger().info('Goal canceled after audio generation.')
                return False, 0.0, 'canceled'

            if audio_buffer is None or play_time <= 0:
                self.get_logger().error(f"Audio buffer generation failed or invalid play time ({play_time:.2f}s) from '{self.tts_name}' model. Check model logs for details.")
                return False, 0.0, 'failed'

            with open(self.output_filepath, 'wb') as f:
                f.write(audio_buffer.getvalue())
            self.get_logger().info(f"Audio successfully saved to: {self.output_filepath}")

            pygame.mixer.music.load(self.output_filepath)
            pygame.mixer.music.play()

            start_playback_loop_time = time.time()
            total_time = 0.0

            while pygame.mixer.music.get_busy():
                if should_cancel():
                    self.get_logger().info('Goal canceled during playback.')
                    pygame.mixer.music.stop()
                    return False, total_time, 'canceled'

                current_time_in_loop = time.time()
                elapsed_in_loop = current_time_in_loop - start_playback_loop_time
                total_time = elapsed_in_loop
                remaining_time = play_time - elapsed_in_loop

                if feedback_callback is not None:
                    feedback_callback(remaining_time, elapsed_in_loop)
                time.sleep(0.05)

            final_elapsed_time = time.time() - start_playback_loop_time
            if feedback_callback is not None:
                feedback_callback(0.0, final_elapsed_time)

            if abs(play_time - final_elapsed_time) < 0.5 or final_elapsed_time >= play_time:
                self.get_logger().info(f"Playback completed. Estimated: {play_time:.2f}s, Actual: {final_elapsed_time:.2f}s")
                return True, final_elapsed_time, 'succeeded'
            else:
                self.get_logger().warn(f"Playback ended prematurely or unexpectedly. Estimated: {play_time:.2f}s, Actual: {final_elapsed_time:.2f}s")
                return False, final_elapsed_time, 'failed'

        except Exception as e:
            self.get_logger().error(f"An unexpected error occurred during audio generation or playback by TTS model: {e}")
            self.get_logger().error(traceback.format_exc())
            try:
                if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()
            except Exception:
                pass
            return False, 0.0, 'failed'

def main(args=None):
    rclpy.init(args=args)
    action_server = None

    try:
        action_server = TTSActionServer()
        executor = MultiThreadedExecutor()
        executor.add_node(action_server)
        executor.spin()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        if action_server:
            action_server.get_logger().error(f"Fatal error: {e}")
        else:
            print(f"Failed to start node: {e}")
    finally:
        if rclpy.ok():
            if action_server:
                action_server.destroy_node()
            rclpy.shutdown()

if __name__ == "__main__":
    main()
