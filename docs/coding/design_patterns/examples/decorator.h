#pragma once
#include <string>
#include <iostream>

namespace decorator_pattern {
// Decorator Pattern: Attaches additional responsibilities to an object dynamically.
// Decorators provide a flexible alternative to subclassing for extending functionality.

// Component interface
struct Beverage {
	virtual ~Beverage() = default;
	virtual std::string GetDescription() const = 0;
	virtual double Cost() const = 0;
};

// Concrete Components
class Espresso : public Beverage {
public:
	std::string GetDescription() const override {
		return "Espresso";
	}

	double Cost() const override {
		return 1.99;
	}
};

class HouseBlend : public Beverage {
public:
	std::string GetDescription() const override {
		return "House Blend Coffee";
	}

	double Cost() const override {
		return 0.89;
	}
};

class DarkRoast : public Beverage {
public:
	std::string GetDescription() const override {
		return "Dark Roast Coffee";
	}

	double Cost() const override {
		return 0.99;
	}
};

class Decaf : public Beverage {
public:
	std::string GetDescription() const override {
		return "Decaf Coffee";
	}

	double Cost() const override {
		return 1.05;
	}
};

// Decorator base class
class CondimentDecorator : public Beverage {
protected:
	Beverage* beverage;

public:
	explicit CondimentDecorator(Beverage* bev) : beverage(bev) {}
	virtual ~CondimentDecorator() = default;
};

// Concrete Decorators
class Mocha : public CondimentDecorator {
public:
	explicit Mocha(Beverage* bev) : CondimentDecorator(bev) {}

	std::string GetDescription() const override {
		return beverage->GetDescription() + ", Mocha";
	}

	double Cost() const override {
		return beverage->Cost() + 0.20;
	}
};

class Soy : public CondimentDecorator {
public:
	explicit Soy(Beverage* bev) : CondimentDecorator(bev) {}

	std::string GetDescription() const override {
		return beverage->GetDescription() + ", Soy";
	}

	double Cost() const override {
		return beverage->Cost() + 0.15;
	}
};

class Whip : public CondimentDecorator {
public:
	explicit Whip(Beverage* bev) : CondimentDecorator(bev) {}

	std::string GetDescription() const override {
		return beverage->GetDescription() + ", Whip";
	}

	double Cost() const override {
		return beverage->Cost() + 0.10;
	}
};

class SteamedMilk : public CondimentDecorator {
public:
	explicit SteamedMilk(Beverage* bev) : CondimentDecorator(bev) {}

	std::string GetDescription() const override {
		return beverage->GetDescription() + ", Steamed Milk";
	}

	double Cost() const override {
		return beverage->Cost() + 0.10;
	}
};

// Usage example
inline void DecoratorPatternDemo() {
	// Order an espresso
	Beverage* beverage1 = new Espresso();
	std::cout << beverage1->GetDescription() << " $" << beverage1->Cost() << "\n";

	// Order a dark roast with double mocha and whip
	Beverage* beverage2 = new DarkRoast();
	beverage2 = new Mocha(beverage2);
	beverage2 = new Mocha(beverage2);
	beverage2 = new Whip(beverage2);
	std::cout << beverage2->GetDescription() << " $" << beverage2->Cost() << "\n";

	// Order a house blend with soy, mocha, and whip
	Beverage* beverage3 = new HouseBlend();
	beverage3 = new Soy(beverage3);
	beverage3 = new Mocha(beverage3);
	beverage3 = new Whip(beverage3);
	std::cout << beverage3->GetDescription() << " $" << beverage3->Cost() << "\n";

	// Clean up (in production, use smart pointers)
	delete beverage1;
	// Note: Need to properly clean up decorator chain in production
}
}  // namespace decorator_pattern