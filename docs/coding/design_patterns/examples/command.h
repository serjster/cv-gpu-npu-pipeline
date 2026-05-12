#pragma once
#include <iostream>
#include <memory>
#include <vector>
#include <stack>

namespace command_pattern {
// Command Pattern: Encapsulates a request as an object, thereby letting you parameterize
// clients with different requests, queue or log requests, and support undoable operations.

// Command interface
struct Command {
	virtual ~Command() = default;
	virtual void Execute() = 0;
	virtual void Undo() = 0;
};

// Receiver: Light
class Light {
private:
	std::string location;

public:
	explicit Light(const std::string& loc) : location(loc) {}

	void On() {
		std::cout << location << " light is ON\n";
	}

	void Off() {
		std::cout << location << " light is OFF\n";
	}
};

// Receiver: CeilingFan
class CeilingFan {
public:
	enum Speed { OFF = 0, LOW = 1, MEDIUM = 2, HIGH = 3 };

private:
	std::string location;
	Speed speed;

public:
	explicit CeilingFan(const std::string& loc) : location(loc), speed(OFF) {}

	void High() {
		speed = HIGH;
		std::cout << location << " ceiling fan is on HIGH\n";
	}

	void Medium() {
		speed = MEDIUM;
		std::cout << location << " ceiling fan is on MEDIUM\n";
	}

	void Low() {
		speed = LOW;
		std::cout << location << " ceiling fan is on LOW\n";
	}

	void Off() {
		speed = OFF;
		std::cout << location << " ceiling fan is OFF\n";
	}

	Speed GetSpeed() const { return speed; }
};

// Receiver: Stereo
class Stereo {
private:
	std::string location;

public:
	explicit Stereo(const std::string& loc) : location(loc) {}

	void On() {
		std::cout << location << " stereo is ON\n";
	}

	void Off() {
		std::cout << location << " stereo is OFF\n";
	}

	void SetCD() {
		std::cout << location << " stereo is set for CD input\n";
	}

	void SetVolume(int volume) {
		std::cout << location << " stereo volume set to " << volume << "\n";
	}
};

// Concrete Commands
class LightOnCommand : public Command {
private:
	Light* light;

public:
	explicit LightOnCommand(Light* l) : light(l) {}

	void Execute() override {
		light->On();
	}

	void Undo() override {
		light->Off();
	}
};

class LightOffCommand : public Command {
private:
	Light* light;

public:
	explicit LightOffCommand(Light* l) : light(l) {}

	void Execute() override {
		light->Off();
	}

	void Undo() override {
		light->On();
	}
};

class CeilingFanHighCommand : public Command {
private:
	CeilingFan* ceilingFan;
	CeilingFan::Speed prevSpeed;

public:
	explicit CeilingFanHighCommand(CeilingFan* cf)
		: ceilingFan(cf), prevSpeed(CeilingFan::OFF) {}

	void Execute() override {
		prevSpeed = ceilingFan->GetSpeed();
		ceilingFan->High();
	}

	void Undo() override {
		switch (prevSpeed) {
			case CeilingFan::HIGH: ceilingFan->High(); break;
			case CeilingFan::MEDIUM: ceilingFan->Medium(); break;
			case CeilingFan::LOW: ceilingFan->Low(); break;
			case CeilingFan::OFF: ceilingFan->Off(); break;
		}
	}
};

class StereoOnWithCDCommand : public Command {
private:
	Stereo* stereo;

public:
	explicit StereoOnWithCDCommand(Stereo* s) : stereo(s) {}

	void Execute() override {
		stereo->On();
		stereo->SetCD();
		stereo->SetVolume(11);
	}

	void Undo() override {
		stereo->Off();
	}
};

// No-op command (Null Object pattern)
class NoCommand : public Command {
public:
	void Execute() override {}
	void Undo() override {}
};

// Macro Command - executes multiple commands
class MacroCommand : public Command {
private:
	std::vector<Command*> commands;

public:
	explicit MacroCommand(const std::vector<Command*>& cmds) : commands(cmds) {}

	void Execute() override {
		for (auto* cmd : commands) {
			cmd->Execute();
		}
	}

	void Undo() override {
		// Undo in reverse order
		for (auto it = commands.rbegin(); it != commands.rend(); ++it) {
			(*it)->Undo();
		}
	}
};

// Invoker: RemoteControl
class RemoteControl {
private:
	static constexpr int NUM_SLOTS = 7;
	Command* onCommands[NUM_SLOTS];
	Command* offCommands[NUM_SLOTS];
	Command* undoCommand;

public:
	RemoteControl() {
		Command* noCommand = new NoCommand();
		for (int i = 0; i < NUM_SLOTS; i++) {
			onCommands[i] = noCommand;
			offCommands[i] = noCommand;
		}
		undoCommand = noCommand;
	}

	void SetCommand(int slot, Command* onCommand, Command* offCommand) {
		onCommands[slot] = onCommand;
		offCommands[slot] = offCommand;
	}

	void OnButtonWasPushed(int slot) {
		onCommands[slot]->Execute();
		undoCommand = onCommands[slot];
	}

	void OffButtonWasPushed(int slot) {
		offCommands[slot]->Execute();
		undoCommand = offCommands[slot];
	}

	void UndoButtonWasPushed() {
		undoCommand->Undo();
	}

	void PrintRemote() const {
		std::cout << "\n------ Remote Control ------\n";
		for (int i = 0; i < NUM_SLOTS; i++) {
			std::cout << "[slot " << i << "] configured\n";
		}
	}
};

// Advanced: Command Queue
class CommandQueue {
private:
	std::vector<Command*> queue;

public:
	void AddCommand(Command* cmd) {
		queue.push_back(cmd);
	}

	void ExecuteAll() {
		for (auto* cmd : queue) {
			cmd->Execute();
		}
		queue.clear();
	}
};

// Usage example
inline void CommandPatternDemo() {
	// Create receivers
	Light* livingRoomLight = new Light("Living Room");
	Light* kitchenLight = new Light("Kitchen");
	CeilingFan* ceilingFan = new CeilingFan("Living Room");
	Stereo* stereo = new Stereo("Living Room");

	// Create commands
	LightOnCommand* livingRoomLightOn = new LightOnCommand(livingRoomLight);
	LightOffCommand* livingRoomLightOff = new LightOffCommand(livingRoomLight);
	LightOnCommand* kitchenLightOn = new LightOnCommand(kitchenLight);
	LightOffCommand* kitchenLightOff = new LightOffCommand(kitchenLight);

	CeilingFanHighCommand* ceilingFanHigh = new CeilingFanHighCommand(ceilingFan);
	StereoOnWithCDCommand* stereoOnWithCD = new StereoOnWithCDCommand(stereo);

	// Setup remote control
	RemoteControl remote;
	remote.SetCommand(0, livingRoomLightOn, livingRoomLightOff);
	remote.SetCommand(1, kitchenLightOn, kitchenLightOff);
	remote.SetCommand(2, ceilingFanHigh, new NoCommand());
	remote.SetCommand(3, stereoOnWithCD, new NoCommand());

	// Test remote control
	remote.PrintRemote();

	std::cout << "\nTesting commands:\n";
	remote.OnButtonWasPushed(0);
	remote.OffButtonWasPushed(0);
	remote.UndoButtonWasPushed();

	remote.OnButtonWasPushed(2);
	remote.UndoButtonWasPushed();

	// Macro command example
	std::cout << "\n=== Macro Command (Party Mode) ===\n";
	std::vector<Command*> partyOn = {livingRoomLightOn, stereoOnWithCD, ceilingFanHigh};
	std::vector<Command*> partyOff = {livingRoomLightOff, new NoCommand(), new NoCommand()};

	MacroCommand* partyOnMacro = new MacroCommand(partyOn);
	MacroCommand* partyOffMacro = new MacroCommand(partyOff);

	remote.SetCommand(4, partyOnMacro, partyOffMacro);
	remote.OnButtonWasPushed(4);
	remote.OffButtonWasPushed(4);

	// Clean up (in production, use smart pointers)
	delete livingRoomLight;
	delete kitchenLight;
	delete ceilingFan;
	delete stereo;
}

// Benefits:
// 1. Decouples object that invokes operation from object that performs it
// 2. Easy to add new commands without changing existing code
// 3. Can assemble commands into composite commands
// 4. Can implement undo/redo
// 5. Can implement logging and transactional systems
// 6. Can queue commands for later execution
}  // namespace command_pattern