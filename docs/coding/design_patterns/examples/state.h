#pragma once
#include <iostream>
#include <string>
#include <random>

namespace state_patterrn {
// State Pattern: Allows an object to alter its behavior when its internal state changes.
// The object will appear to change its class.

// Forward declaration
class GumballMachine;

// State interface
class State {
public:
	virtual ~State() = default;
	virtual void InsertQuarter() = 0;
	virtual void EjectQuarter() = 0;
	virtual void TurnCrank() = 0;
	virtual void Dispense() = 0;
	virtual void Refill() {}
	virtual std::string ToString() const = 0;
};

// Context - Gumball Machine
class GumballMachine {
private:
	State* soldOutState;
	State* noQuarterState;
	State* hasQuarterState;
	State* soldState;
	State* winnerState;

	State* state;
	int count;

public:
	GumballMachine(int numberGumballs);
	~GumballMachine();

	void InsertQuarter() { state->InsertQuarter(); }
	void EjectQuarter() { state->EjectQuarter(); }
	void TurnCrank() {
		state->TurnCrank();
		state->Dispense();
	}

	void SetState(State* s) { state = s; }
	void ReleaseBall() {
		std::cout << "A gumball comes rolling out the slot...\n";
		if (count > 0) {
			count--;
		}
	}

	void Refill(int numGumballs) {
		count += numGumballs;
		std::cout << "The gumball machine was just refilled; new count is: " << count << "\n";
		state->Refill();
	}

	int GetCount() const { return count; }

	State* GetSoldOutState() { return soldOutState; }
	State* GetNoQuarterState() { return noQuarterState; }
	State* GetHasQuarterState() { return hasQuarterState; }
	State* GetSoldState() { return soldState; }
	State* GetWinnerState() { return winnerState; }

	std::string ToString() const {
		std::string result = "\nMighty Gumball, Inc.\n";
		result += "C++-enabled Standing Gumball Model #2024\n";
		result += "Inventory: " + std::to_string(count) + " gumball";
		if (count != 1) result += "s";
		result += "\n";
		result += "Machine is " + state->ToString() + "\n";
		return result;
	}
};

// Concrete States
class SoldOutState : public State {
private:
	GumballMachine* gumballMachine;

public:
	explicit SoldOutState(GumballMachine* machine) : gumballMachine(machine) {}

	void InsertQuarter() override {
		std::cout << "You can't insert a quarter, the machine is sold out\n";
	}

	void EjectQuarter() override {
		std::cout << "You can't eject, you haven't inserted a quarter yet\n";
	}

	void TurnCrank() override {
		std::cout << "You turned, but there are no gumballs\n";
	}

	void Dispense() override {
		std::cout << "No gumball dispensed\n";
	}

	void Refill() override {
		gumballMachine->SetState(gumballMachine->GetNoQuarterState());
	}

	std::string ToString() const override {
		return "sold out";
	}
};

class NoQuarterState : public State {
private:
	GumballMachine* gumballMachine;

public:
	explicit NoQuarterState(GumballMachine* machine) : gumballMachine(machine) {}

	void InsertQuarter() override {
		std::cout << "You inserted a quarter\n";
		gumballMachine->SetState(gumballMachine->GetHasQuarterState());
	}

	void EjectQuarter() override {
		std::cout << "You haven't inserted a quarter\n";
	}

	void TurnCrank() override {
		std::cout << "You turned, but there's no quarter\n";
	}

	void Dispense() override {
		std::cout << "You need to pay first\n";
	}

	std::string ToString() const override {
		return "waiting for quarter";
	}
};

class HasQuarterState : public State {
private:
	GumballMachine* gumballMachine;
	std::random_device rd;
	mutable std::mt19937 gen;

public:
	explicit HasQuarterState(GumballMachine* machine)
		: gumballMachine(machine), gen(rd()) {}

	void InsertQuarter() override {
		std::cout << "You can't insert another quarter\n";
	}

	void EjectQuarter() override {
		std::cout << "Quarter returned\n";
		gumballMachine->SetState(gumballMachine->GetNoQuarterState());
	}

	void TurnCrank() override {
		std::cout << "You turned...\n";
		std::uniform_int_distribution<> dis(0, 9);
		int winner = dis(gen);

		if ((winner == 0) && (gumballMachine->GetCount() > 1)) {
			gumballMachine->SetState(gumballMachine->GetWinnerState());
		} else {
			gumballMachine->SetState(gumballMachine->GetSoldState());
		}
	}

	void Dispense() override {
		std::cout << "No gumball dispensed\n";
	}

	std::string ToString() const override {
		return "waiting for turn of crank";
	}
};

class SoldState : public State {
private:
	GumballMachine* gumballMachine;

public:
	explicit SoldState(GumballMachine* machine) : gumballMachine(machine) {}

	void InsertQuarter() override {
		std::cout << "Please wait, we're already giving you a gumball\n";
	}

	void EjectQuarter() override {
		std::cout << "Sorry, you already turned the crank\n";
	}

	void TurnCrank() override {
		std::cout << "Turning twice doesn't get you another gumball!\n";
	}

	void Dispense() override {
		gumballMachine->ReleaseBall();
		if (gumballMachine->GetCount() > 0) {
			gumballMachine->SetState(gumballMachine->GetNoQuarterState());
		} else {
			std::cout << "Oops, out of gumballs!\n";
			gumballMachine->SetState(gumballMachine->GetSoldOutState());
		}
	}

	std::string ToString() const override {
		return "dispensing a gumball";
	}
};

class WinnerState : public State {
private:
	GumballMachine* gumballMachine;

public:
	explicit WinnerState(GumballMachine* machine) : gumballMachine(machine) {}

	void InsertQuarter() override {
		std::cout << "Please wait, we're already giving you a gumball\n";
	}

	void EjectQuarter() override {
		std::cout << "Sorry, you already turned the crank\n";
	}

	void TurnCrank() override {
		std::cout << "Turning twice doesn't get you another gumball!\n";
	}

	void Dispense() override {
		gumballMachine->ReleaseBall();
		if (gumballMachine->GetCount() == 0) {
			gumballMachine->SetState(gumballMachine->GetSoldOutState());
		} else {
			std::cout << "YOU'RE A WINNER! You got two gumballs for your quarter\n";
			gumballMachine->ReleaseBall();

			if (gumballMachine->GetCount() > 0) {
				gumballMachine->SetState(gumballMachine->GetNoQuarterState());
			} else {
				std::cout << "Oops, out of gumballs!\n";
				gumballMachine->SetState(gumballMachine->GetSoldOutState());
			}
		}
	}

	std::string ToString() const override {
		return "despensing two gumballs for your quarter, because YOU'RE A WINNER!";
	}
};

// GumballMachine constructor implementation
GumballMachine::GumballMachine(int numberGumballs) : count(numberGumballs) {
	soldOutState = new SoldOutState(this);
	noQuarterState = new NoQuarterState(this);
	hasQuarterState = new HasQuarterState(this);
	soldState = new SoldState(this);
	winnerState = new WinnerState(this);

	if (numberGumballs > 0) {
		state = noQuarterState;
	} else {
		state = soldOutState;
	}
}

GumballMachine::~GumballMachine() {
	delete soldOutState;
	delete noQuarterState;
	delete hasQuarterState;
	delete soldState;
	delete winnerState;
}

// Another example: TCP Connection
class TCPConnection;

class TCPState {
public:
	virtual ~TCPState() = default;
	virtual void Open(TCPConnection* connection) = 0;
	virtual void Close(TCPConnection* connection) = 0;
	virtual void Acknowledge(TCPConnection* connection) = 0;
};

class TCPConnection {
private:
	TCPState* state;

public:
	explicit TCPConnection(TCPState* s) : state(s) {}

	void SetState(TCPState* s) {
		std::cout << "Changing state\n";
		state = s;
	}

	void Open() { state->Open(this); }
	void Close() { state->Close(this); }
	void Acknowledge() { state->Acknowledge(this); }
};

class TCPEstablished : public TCPState {
public:
	void Open(TCPConnection*) override {
		std::cout << "Connection already open\n";
	}

	void Close(TCPConnection* connection) override {
		std::cout << "Closing connection\n";
		// Change to closed state
	}

	void Acknowledge(TCPConnection*) override {
		std::cout << "Acknowledging data\n";
	}
};

// Usage example
inline void StatePatternDemo() {
	std::cout << "=== Gumball Machine Demo ===\n";

	GumballMachine* gumballMachine = new GumballMachine(5);

	std::cout << gumballMachine->ToString();

	gumballMachine->InsertQuarter();
	gumballMachine->TurnCrank();

	std::cout << gumballMachine->ToString();

	gumballMachine->InsertQuarter();
	gumballMachine->TurnCrank();
	gumballMachine->InsertQuarter();
	gumballMachine->TurnCrank();

	std::cout << gumballMachine->ToString();

	// Refill
	gumballMachine->Refill(5);
	std::cout << gumballMachine->ToString();

	delete gumballMachine;
}

// State Pattern vs Strategy Pattern:
// - State: Behavior changes based on internal state, context controls state transitions
// - Strategy: Client chooses which strategy to use, strategies are interchangeable
// - State: States often know about each other and trigger transitions
// - Strategy: Strategies are independent and don't know about each other

// State Pattern vs State Machine:
// - State Pattern: Object-oriented approach, each state is a class
// - State Machine: Often implemented with switch/if statements
// - State Pattern: Easier to add new states (Open/Closed Principle)
// - State Machine: Can be simpler for small state machines

// Benefits:
// 1. Localizes state-specific behavior
// 2. Makes state transitions explicit
// 3. State objects can be shared (if they have no instance variables)
// 4. Eliminates large conditional statements
// 5. Easy to add new states

// When to use State:
// 1. Object behavior depends on its state
// 2. Operations have large conditional statements depending on state
// 3. State transitions are explicit and need to be managed
}  // namespace state_patterrn