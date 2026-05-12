#pragma once
#include <iostream>
#include <vector>
#include <string>
#include <memory>

// Compound Patterns: Combining two or more patterns into a solution that solves
// a recurring or general problem.

// Example: Model-View-Controller (MVC) combines Observer, Strategy, and Composite

namespace compound_pattern {

// Model-View-Controller Example: Beat Model

// Observable interface (part of Observer pattern)
class BeatObserver {
public:
	virtual ~BeatObserver() = default;
	virtual void BeatEvent() = 0;
};

class BPMObserver {
public:
	virtual ~BPMObserver() = default;
	virtual void BPMEvent(int bpm) = 0;
};

// Model interface
class BeatModelInterface {
public:
	virtual ~BeatModelInterface() = default;

	virtual void Initialize() = 0;
	virtual void On() = 0;
	virtual void Off() = 0;
	virtual void SetBPM(int bpm) = 0;
	virtual int GetBPM() const = 0;

	virtual void RegisterBeatObserver(BeatObserver* observer) = 0;
	virtual void RemoveBeatObserver(BeatObserver* observer) = 0;
	virtual void RegisterBPMObserver(BPMObserver* observer) = 0;
	virtual void RemoveBPMObserver(BPMObserver* observer) = 0;
};

// Concrete Model (Observable)
class BeatModel : public BeatModelInterface {
private:
	std::vector<BeatObserver*> beatObservers;
	std::vector<BPMObserver*> bpmObservers;
	int bpm;
	bool playing;

	void NotifyBeatObservers() {
		for (auto* observer : beatObservers) {
			observer->BeatEvent();
		}
	}

	void NotifyBPMObservers() {
		for (auto* observer : bpmObservers) {
			observer->BPMEvent(bpm);
		}
	}

public:
	BeatModel() : bpm(90), playing(false) {}

	void Initialize() override {
		// Initialize audio, etc.
		std::cout << "Beat model initialized\n";
	}

	void On() override {
		playing = true;
		std::cout << "Beat started at " << bpm << " BPM\n";
		NotifyBeatObservers();
	}

	void Off() override {
		playing = false;
		std::cout << "Beat stopped\n";
	}

	void SetBPM(int newBpm) override {
		bpm = newBpm;
		NotifyBPMObservers();
		std::cout << "BPM changed to " << bpm << "\n";
	}

	int GetBPM() const override {
		return bpm;
	}

	void RegisterBeatObserver(BeatObserver* observer) override {
		beatObservers.push_back(observer);
	}

	void RemoveBeatObserver(BeatObserver* observer) override {
		auto it = std::find(beatObservers.begin(), beatObservers.end(), observer);
		if (it != beatObservers.end()) {
			beatObservers.erase(it);
		}
	}

	void RegisterBPMObserver(BPMObserver* observer) override {
		bpmObservers.push_back(observer);
	}

	void RemoveBPMObserver(BPMObserver* observer) override {
		auto it = std::find(bpmObservers.begin(), bpmObservers.end(), observer);
		if (it != bpmObservers.end()) {
			bpmObservers.erase(it);
		}
	}
};

// View
class DJView : public BeatObserver, public BPMObserver {
private:
	BeatModelInterface* model;
	std::string viewName;

public:
	DJView(BeatModelInterface* m, const std::string& name)
		: model(m), viewName(name) {
		model->RegisterBeatObserver(this);
		model->RegisterBPMObserver(this);
	}

	void BeatEvent() override {
		std::cout << "[" << viewName << " View] Beat pulse displayed\n";
	}

	void BPMEvent(int bpm) override {
		std::cout << "[" << viewName << " View] BPM display updated to " << bpm << "\n";
	}

	void Display() {
		std::cout << "[" << viewName << " View] Current BPM: " << model->GetBPM() << "\n";
	}
};

// Controller (uses Strategy-like pattern)
class ControllerInterface {
public:
	virtual ~ControllerInterface() = default;
	virtual void Start() = 0;
	virtual void Stop() = 0;
	virtual void IncreaseBPM() = 0;
	virtual void DecreaseBPM() = 0;
	virtual void SetBPM(int bpm) = 0;
};

class BeatController : public ControllerInterface {
private:
	BeatModelInterface* model;
	DJView* view;

public:
	BeatController(BeatModelInterface* m) : model(m), view(nullptr) {
		view = new DJView(model, "DJ");
	}

	~BeatController() {
		delete view;
	}

	void Start() override {
		model->On();
	}

	void Stop() override {
		model->Off();
	}

	void IncreaseBPM() override {
		int bpm = model->GetBPM();
		model->SetBPM(bpm + 1);
	}

	void DecreaseBPM() override {
		int bpm = model->GetBPM();
		model->SetBPM(bpm - 1);
	}

	void SetBPM(int bpm) override {
		model->SetBPM(bpm);
	}
};

// Another Compound Pattern Example: Duck Simulator
// Combines: Factory, Adapter, Composite, Decorator, Observer

// Quackable interface
class QuackObservable;

class Quackable {
public:
	virtual ~Quackable() = default;
	virtual void Quack() = 0;
	virtual QuackObservable* GetQuackObservable() = 0;
};

// Observer for quacking
class QuackObserver {
public:
	virtual ~QuackObserver() = default;
	virtual void Update(Quackable* duck) = 0;
};

// Observable aspect
class QuackObservable {
public:
	virtual ~QuackObservable() = default;
	virtual void RegisterObserver(QuackObserver* observer) = 0;
	virtual void NotifyObservers() = 0;
};

// Concrete Observable
class Observable : public QuackObservable {
private:
	std::vector<QuackObserver*> observers;
	Quackable* duck;

public:
	explicit Observable(Quackable* d) : duck(d) {}

	void RegisterObserver(QuackObserver* observer) override {
		observers.push_back(observer);
	}

	void NotifyObservers() override {
		for (auto* observer : observers) {
			observer->Update(duck);
		}
	}
};

// Concrete Quackables
class MallardDuck : public Quackable {
private:
	Observable* observable;

public:
	MallardDuck() : observable(new Observable(this)) {}

	~MallardDuck() {
		delete observable;
	}

	void Quack() override {
		std::cout << "Mallard: Quack\n";
		observable->NotifyObservers();
	}

	QuackObservable* GetQuackObservable() override {
		return observable;
	}
};

class RedheadDuck : public Quackable {
private:
	Observable* observable;

public:
	RedheadDuck() : observable(new Observable(this)) {}

	~RedheadDuck() {
		delete observable;
	}

	void Quack() override {
		std::cout << "Redhead: Quack\n";
		observable->NotifyObservers();
	}

	QuackObservable* GetQuackObservable() override {
		return observable;
	}
};

class RubberDuck : public Quackable {
private:
	Observable* observable;

public:
	RubberDuck() : observable(new Observable(this)) {}

	~RubberDuck() {
		delete observable;
	}

	void Quack() override {
		std::cout << "Rubber: Squeak\n";
		observable->NotifyObservers();
	}

	QuackObservable* GetQuackObservable() override {
		return observable;
	}
};

class Goose {
public:
	void Honk() {
		std::cout << "Goose: Honk\n";
	}
};

// Adapter - makes Goose look like Quackable
class GooseAdapter : public Quackable {
private:
	Goose* goose;
	Observable* observable;

public:
	explicit GooseAdapter(Goose* g) : goose(g), observable(new Observable(this)) {}

	~GooseAdapter() {
		delete observable;
	}

	void Quack() override {
		goose->Honk();
		observable->NotifyObservers();
	}

	QuackObservable* GetQuackObservable() override {
		return observable;
	}
};

// Decorator - adds counting functionality
class QuackCounter : public Quackable {
private:
	Quackable* duck;
	static int numberOfQuacks;

public:
	explicit QuackCounter(Quackable* d) : duck(d) {}

	void Quack() override {
		duck->Quack();
		numberOfQuacks++;
	}

	QuackObservable* GetQuackObservable() override {
		return duck->GetQuackObservable();
	}

	static int GetQuacks() {
		return numberOfQuacks;
	}
};

int QuackCounter::numberOfQuacks = 0;

// Composite - group of ducks
class Flock : public Quackable {
private:
	std::vector<Quackable*> ducks;
	Observable* observable;

public:
	Flock() : observable(new Observable(this)) {}

	~Flock() {
		delete observable;
	}

	void Add(Quackable* duck) {
		ducks.push_back(duck);
	}

	void Quack() override {
		for (auto* duck : ducks) {
			duck->Quack();
		}
		observable->NotifyObservers();
	}

	QuackObservable* GetQuackObservable() override {
		return observable;
	}
};

// Abstract Factory
class AbstractDuckFactory {
public:
	virtual ~AbstractDuckFactory() = default;
	virtual Quackable* CreateMallardDuck() = 0;
	virtual Quackable* CreateRedheadDuck() = 0;
	virtual Quackable* CreateRubberDuck() = 0;
};

class DuckFactory : public AbstractDuckFactory {
public:
	Quackable* CreateMallardDuck() override {
		return new MallardDuck();
	}

	Quackable* CreateRedheadDuck() override {
		return new RedheadDuck();
	}

	Quackable* CreateRubberDuck() override {
		return new RubberDuck();
	}
};

class CountingDuckFactory : public AbstractDuckFactory {
public:
	Quackable* CreateMallardDuck() override {
		return new QuackCounter(new MallardDuck());
	}

	Quackable* CreateRedheadDuck() override {
		return new QuackCounter(new RedheadDuck());
	}

	Quackable* CreateRubberDuck() override {
		return new QuackCounter(new RubberDuck());
	}
};

// Concrete Observer
class Quackologist : public QuackObserver {
public:
	void Update(Quackable* duck) override {
		std::cout << "Quackologist: Duck just quacked!\n";
	}
};

// Usage example
inline void CompoundPatternDemo() {
	std::cout << "=== MVC Pattern Demo ===\n";

	BeatModel* model = new BeatModel();
	BeatController* controller = new BeatController(model);

	model->Initialize();
	model->SetBPM(120);
	controller->Start();
	controller->IncreaseBPM();
	controller->IncreaseBPM();
	controller->Stop();

	delete controller;
	delete model;

	std::cout << "\n=== Duck Simulator (Multiple Patterns) ===\n";

	AbstractDuckFactory* duckFactory = new CountingDuckFactory();

	Quackable* mallard = duckFactory->CreateMallardDuck();
	Quackable* redhead = duckFactory->CreateRedheadDuck();
	Quackable* rubber = duckFactory->CreateRubberDuck();
	Quackable* goose = new GooseAdapter(new Goose());

	// Create flock (Composite)
	Flock* flockOfDucks = new Flock();
	flockOfDucks->Add(mallard);
	flockOfDucks->Add(redhead);
	flockOfDucks->Add(rubber);
	flockOfDucks->Add(goose);

	// Create subflock
	Flock* flockOfMallards = new Flock();
	flockOfMallards->Add(duckFactory->CreateMallardDuck());
	flockOfMallards->Add(duckFactory->CreateMallardDuck());

	flockOfDucks->Add(flockOfMallards);

	// Add observer
	Quackologist* quackologist = new Quackologist();
	flockOfDucks->GetQuackObservable()->RegisterObserver(quackologist);

	std::cout << "\nDuck Simulator: Whole Flock Simulation\n";
	flockOfDucks->Quack();

	std::cout << "\nDuck Simulator: Mallard Flock Simulation\n";
	flockOfMallards->Quack();

	std::cout << "\nThe ducks quacked " << QuackCounter::GetQuacks() << " times\n";

	// Clean up
	delete flockOfDucks;
	delete flockOfMallards;
	delete duckFactory;
	delete quackologist;
}

// Patterns used in the Duck Simulator:
// 1. Factory - creates ducks
// 2. Abstract Factory - family of duck products
// 3. Adapter - makes Goose compatible with Quackable
// 4. Composite - Flock manages collection of Quackables
// 5. Decorator - QuackCounter adds counting behavior
// 6. Observer - Quackologist observes quacking
// 7. Iterator - (implicitly used when traversing flock)

// MVC Pattern breakdown:
// - Model: Holds data and business logic (Observable - Observer pattern)
// - View: Displays model to user (Observer of Model)
// - Controller: Takes user input and manipulates model (Strategy pattern)
//
// Benefits:
// 1. Decouples model from view
// 2. Multiple views can observe same model
// 3. Easy to test model independently
// 4. Can change view without changing model
// 5. Can change controller behavior (Strategy)

// When to use Compound Patterns:
// 1. Problem requires multiple patterns working together
// 2. Building complex systems with clear separation of concerns
// 3. Need flexibility to change different aspects independently
// 4. Want to leverage proven pattern combinations

} // namespace CompoundPattern
