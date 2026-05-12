#pragma once
#include <iostream>
#include <string>

// Adapter Pattern: Converts the interface of a class into another interface clients expect.
// Adapter lets classes work together that couldn't otherwise because of incompatible interfaces.

namespace adapter_pattern {

// Target interface - what the client expects
struct Duck {
	virtual ~Duck() = default;
	virtual void Quack() = 0;
	virtual void Fly() = 0;
};

// Adaptee - existing interface that needs adapting
struct Turkey {
	virtual ~Turkey() = default;
	virtual void Gobble() = 0;
	virtual void Fly() = 0;
};

// Concrete Adaptee
class WildTurkey : public Turkey {
public:
	void Gobble() override {
		std::cout << "Gobble gobble\n";
	}

	void Fly() override {
		std::cout << "I'm flying a short distance\n";
	}
};

// Adapter - makes Turkey look like Duck
class TurkeyAdapter : public Duck {
private:
	Turkey* turkey;

public:
	explicit TurkeyAdapter(Turkey* t) : turkey(t) {}

	void Quack() override {
		turkey->Gobble();
	}

	void Fly() override {
		// Turkeys fly short distances, so fly 5 times to match duck
		for (int i = 0; i < 5; i++) {
			turkey->Fly();
		}
	}
};

// Concrete Target
class MallardDuck : public Duck {
public:
	void Quack() override {
		std::cout << "Quack\n";
	}

	void Fly() override {
		std::cout << "I'm flying\n";
	}
};

// Reverse adapter example
class DuckAdapter : public Turkey {
private:
	Duck* duck;

public:
	explicit DuckAdapter(Duck* d) : duck(d) {}

	void Gobble() override {
		duck->Quack();
	}

	void Fly() override {
		duck->Fly();
	}
};

// Real-world example: Enumeration to Iterator adapter
// (This demonstrates adapting old interfaces to new ones)

template<typename T>
class Enumeration {
public:
	virtual ~Enumeration() = default;
	virtual bool HasMoreElements() = 0;
	virtual T NextElement() = 0;
};

template<typename T>
class Iterator {
public:
	virtual ~Iterator() = default;
	virtual bool HasNext() = 0;
	virtual T Next() = 0;
	virtual void Remove() = 0;
};

template<typename T>
class EnumerationIterator : public Iterator<T> {
private:
	Enumeration<T>* enumeration;

public:
	explicit EnumerationIterator(Enumeration<T>* e) : enumeration(e) {}

	bool HasNext() override {
		return enumeration->HasMoreElements();
	}

	T Next() override {
		return enumeration->NextElement();
	}

	void Remove() override {
		throw std::runtime_error("Unsupported operation");
	}
};

// Two-way adapter (both Duck and Turkey)
class BidirectionalAdapter : public Duck, public Turkey {
private:
	Duck* duck;

public:
	explicit BidirectionalAdapter(Duck* d) : duck(d) {}

	// Duck interface
	void Quack() override {
		duck->Quack();
	}

	void Fly() override {
		duck->Fly();
	}

	// Turkey interface
	void Gobble() override {
		duck->Quack(); // Adapt quack to gobble
	}
};

// Client code
inline void TestDuck(Duck* duck) {
	duck->Quack();
	duck->Fly();
}

inline void TestTurkey(Turkey* turkey) {
	turkey->Gobble();
	turkey->Fly();
}

// Usage example
inline void AdapterPatternDemo() {
	std::cout << "=== Duck Test ===\n";
	MallardDuck* duck = new MallardDuck();
	TestDuck(duck);

	std::cout << "\n=== Turkey Test ===\n";
	WildTurkey* turkey = new WildTurkey();
	TestTurkey(turkey);

	std::cout << "\n=== Turkey Adapter Test (Turkey pretending to be Duck) ===\n";
	Duck* turkeyAdapter = new TurkeyAdapter(turkey);
	TestDuck(turkeyAdapter);

	std::cout << "\n=== Duck Adapter Test (Duck pretending to be Turkey) ===\n";
	Turkey* duckAdapter = new DuckAdapter(duck);
	TestTurkey(duckAdapter);

	delete duck;
	delete turkey;
	delete turkeyAdapter;
	delete duckAdapter;
}

// Object Adapter vs Class Adapter:
// - Object Adapter (shown above): Uses composition, more flexible
// - Class Adapter: Uses multiple inheritance, less flexible but can override adaptee behavior

// When to use Adapter:
// 1. Want to use existing class but interface doesn't match what you need
// 2. Want to create reusable class that cooperates with unrelated classes
// 3. Need to use several existing subclasses but impractical to adapt by subclassing
// 4. Integrating legacy code with new systems

} // namespace AdapterPattern
