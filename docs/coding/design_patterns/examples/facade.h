#pragma once
#include <iostream>
#include <string>

namespace facade_pattern {
// Facade Pattern: Provides a unified interface to a set of interfaces in a subsystem.
// Facade defines a higher-level interface that makes the subsystem easier to use.

// Subsystem classes - complex system with many components
class Amplifier {
private:
	std::string description;

public:
	explicit Amplifier(const std::string& desc) : description(desc) {}

	void On() {
		std::cout << description << " on\n";
	}

	void Off() {
		std::cout << description << " off\n";
	}

	void SetStreamingPlayer(const std::string& player) {
		std::cout << description << " setting streaming player to " << player << "\n";
	}

	void SetSurroundSound() {
		std::cout << description << " surround sound on (5 speakers, 1 subwoofer)\n";
	}

	void SetVolume(int level) {
		std::cout << description << " setting volume to " << level << "\n";
	}
};

class StreamingPlayer {
private:
	std::string description;
	std::string currentMovie;

public:
	explicit StreamingPlayer(const std::string& desc) : description(desc) {}

	void On() {
		std::cout << description << " on\n";
	}

	void Off() {
		std::cout << description << " off\n";
	}

	void Play(const std::string& movie) {
		currentMovie = movie;
		std::cout << description << " playing \"" << movie << "\"\n";
	}

	void Stop() {
		std::cout << description << " stopped \"" << currentMovie << "\"\n";
	}

	void Pause() {
		std::cout << description << " paused \"" << currentMovie << "\"\n";
	}
};

class Projector {
private:
	std::string description;

public:
	explicit Projector(const std::string& desc) : description(desc) {}

	void On() {
		std::cout << description << " on\n";
	}

	void Off() {
		std::cout << description << " off\n";
	}

	void WideScreenMode() {
		std::cout << description << " in widescreen mode (16x9 aspect ratio)\n";
	}
};

class TheaterLights {
private:
	std::string description;

public:
	explicit TheaterLights(const std::string& desc) : description(desc) {}

	void On() {
		std::cout << description << " on\n";
	}

	void Off() {
		std::cout << description << " off\n";
	}

	void Dim(int level) {
		std::cout << description << " dimming to " << level << "%\n";
	}
};

class Screen {
private:
	std::string description;

public:
	explicit Screen(const std::string& desc) : description(desc) {}

	void Up() {
		std::cout << description << " going up\n";
	}

	void Down() {
		std::cout << description << " going down\n";
	}
};

class PopcornPopper {
private:
	std::string description;

public:
	explicit PopcornPopper(const std::string& desc) : description(desc) {}

	void On() {
		std::cout << description << " on\n";
	}

	void Off() {
		std::cout << description << " off\n";
	}

	void Pop() {
		std::cout << description << " popping popcorn!\n";
	}
};

// Facade - simplified interface to the complex subsystem
class HomeTheaterFacade {
private:
	Amplifier* amp;
	StreamingPlayer* player;
	Projector* projector;
	TheaterLights* lights;
	Screen* screen;
	PopcornPopper* popper;

public:
	HomeTheaterFacade(
		Amplifier* a,
		StreamingPlayer* p,
		Projector* proj,
		TheaterLights* l,
		Screen* s,
		PopcornPopper* pop
	) : amp(a), player(p), projector(proj), lights(l), screen(s), popper(pop) {}

	// High-level methods that use the subsystem
	void WatchMovie(const std::string& movie) {
		std::cout << "Get ready to watch a movie...\n";
		popper->On();
		popper->Pop();
		lights->Dim(10);
		screen->Down();
		projector->On();
		projector->WideScreenMode();
		amp->On();
		amp->SetStreamingPlayer("Streaming Player");
		amp->SetSurroundSound();
		amp->SetVolume(5);
		player->On();
		player->Play(movie);
	}

	void EndMovie() {
		std::cout << "Shutting movie theater down...\n";
		popper->Off();
		lights->On();
		screen->Up();
		projector->Off();
		amp->Off();
		player->Stop();
		player->Off();
	}

	void ListenToRadio(double frequency) {
		std::cout << "Tuning in the radio...\n";
		amp->On();
		amp->SetVolume(5);
		// Would tune radio to frequency
		std::cout << "Radio tuned to " << frequency << " FM\n";
	}

	void EndRadio() {
		std::cout << "Shutting down the radio...\n";
		amp->Off();
	}
};

// Without Facade, client would need to do this:
inline void WatchMovieWithoutFacade(
	PopcornPopper* popper,
	TheaterLights* lights,
	Screen* screen,
	Projector* projector,
	Amplifier* amp,
	StreamingPlayer* player,
	const std::string& movie
) {
	popper->On();
	popper->Pop();
	lights->Dim(10);
	screen->Down();
	projector->On();
	projector->WideScreenMode();
	amp->On();
	amp->SetStreamingPlayer("Streaming Player");
	amp->SetSurroundSound();
	amp->SetVolume(5);
	player->On();
	player->Play(movie);
	// And to stop, need to reverse all of this...
}

// Usage example
inline void FacadePatternDemo() {
	// Create all subsystem components
	Amplifier* amp = new Amplifier("Top-O-Line Amplifier");
	StreamingPlayer* player = new StreamingPlayer("Top-O-Line Streaming Player");
	Projector* projector = new Projector("Top-O-Line Projector");
	TheaterLights* lights = new TheaterLights("Theater Ceiling Lights");
	Screen* screen = new Screen("Theater Screen");
	PopcornPopper* popper = new PopcornPopper("Popcorn Popper");

	// Create facade
	HomeTheaterFacade* homeTheater = new HomeTheaterFacade(
		amp, player, projector, lights, screen, popper
	);

	// Simple interface - much easier!
	homeTheater->WatchMovie("Raiders of the Lost Ark");
	std::cout << "\n";
	homeTheater->EndMovie();

	// Clean up
	delete amp;
	delete player;
	delete projector;
	delete lights;
	delete screen;
	delete popper;
	delete homeTheater;
}

// Benefits of Facade:
// 1. Simplifies interface to complex subsystem
// 2. Decouples client from subsystem components
// 3. Doesn't prevent accessing subsystem classes directly if needed
// 4. Adheres to Principle of Least Knowledge (Law of Demeter)

// Principle of Least Knowledge (Law of Demeter):
// Talk only to your immediate friends. Don't talk to strangers.
//
// Guidelines:
// An object's method should only call methods of:
// 1. The object itself
// 2. Objects passed as parameters
// 3. Objects it creates/instantiates
// 4. Components of the object (has-a relationship)
//
// DON'T call methods on objects returned from other methods

// Example of violating Law of Demeter:
inline float GetTempBad() {
	// BAD: Chaining through multiple objects
	// return station->GetThermometer()->GetTemperature();
	return 0.0f;
}

// Example of following Law of Demeter:
inline float GetTempGood() {
	// GOOD: Ask station for temperature (it handles thermometer internally)
	// return station->GetTemperature();
	return 0.0f;
}

// When to use Facade:
// 1. Want to provide simple interface to complex subsystem
// 2. Many dependencies between clients and implementation classes
// 3. Want to layer your subsystems
// 4. Want to minimize coupling between subsystems
}  // namespace facade_pattern