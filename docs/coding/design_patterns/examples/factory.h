#pragma once
#include <string>
#include <iostream>
#include <memory>

namespace factory_pattern {
// Factory Pattern: Defines an interface for creating an object, but lets subclasses
// decide which class to instantiate. Factory Method lets a class defer instantiation
// to subclasses.

// Product interface
struct Pizza {
	virtual ~Pizza() = default;
	std::string name;
	std::string dough;
	std::string sauce;

	virtual void Prepare() {
		std::cout << "Preparing " << name << "\n";
		std::cout << "Tossing dough: " << dough << "\n";
		std::cout << "Adding sauce: " << sauce << "\n";
	}

	virtual void Bake() {
		std::cout << "Bake for 25 minutes at 350\n";
	}

	virtual void Cut() {
		std::cout << "Cutting the pizza into diagonal slices\n";
	}

	virtual void Box() {
		std::cout << "Place pizza in official PizzaStore box\n";
	}

	std::string GetName() const {
		return name;
	}
};

// Concrete Products - NY Style
class NYStyleCheesePizza : public Pizza {
public:
	NYStyleCheesePizza() {
		name = "NY Style Sauce and Cheese Pizza";
		dough = "Thin Crust Dough";
		sauce = "Marinara Sauce";
	}
};

class NYStylePepperoniPizza : public Pizza {
public:
	NYStylePepperoniPizza() {
		name = "NY Style Pepperoni Pizza";
		dough = "Thin Crust Dough";
		sauce = "Marinara Sauce";
	}
};

class NYStyleVeggiePizza : public Pizza {
public:
	NYStyleVeggiePizza() {
		name = "NY Style Veggie Pizza";
		dough = "Thin Crust Dough";
		sauce = "Marinara Sauce";
	}
};

// Concrete Products - Chicago Style
class ChicagoStyleCheesePizza : public Pizza {
public:
	ChicagoStyleCheesePizza() {
		name = "Chicago Style Deep Dish Cheese Pizza";
		dough = "Extra Thick Crust Dough";
		sauce = "Plum Tomato Sauce";
	}

	void Cut() override {
		std::cout << "Cutting the pizza into square slices\n";
	}
};

class ChicagoStylePepperoniPizza : public Pizza {
public:
	ChicagoStylePepperoniPizza() {
		name = "Chicago Style Pepperoni Pizza";
		dough = "Extra Thick Crust Dough";
		sauce = "Plum Tomato Sauce";
	}

	void Cut() override {
		std::cout << "Cutting the pizza into square slices\n";
	}
};

class ChicagoStyleVeggiePizza : public Pizza {
public:
	ChicagoStyleVeggiePizza() {
		name = "Chicago Deep Dish Veggie Pizza";
		dough = "Extra Thick Crust Dough";
		sauce = "Plum Tomato Sauce";
	}

	void Cut() override {
		std::cout << "Cutting the pizza into square slices\n";
	}
};

// Creator (Factory Method)
class PizzaStore {
public:
	virtual ~PizzaStore() = default;

	std::unique_ptr<Pizza> OrderPizza(const std::string& type) {
		auto pizza = CreatePizza(type);

		if (pizza) {
			pizza->Prepare();
			pizza->Bake();
			pizza->Cut();
			pizza->Box();
		}

		return pizza;
	}

protected:
	// Factory method - subclasses implement this
	virtual std::unique_ptr<Pizza> CreatePizza(const std::string& type) = 0;
};

// Concrete Creators
class NYPizzaStore : public PizzaStore {
protected:
	std::unique_ptr<Pizza> CreatePizza(const std::string& type) override {
		if (type == "cheese") {
			return std::make_unique<NYStyleCheesePizza>();
		} else if (type == "pepperoni") {
			return std::make_unique<NYStylePepperoniPizza>();
		} else if (type == "veggie") {
			return std::make_unique<NYStyleVeggiePizza>();
		}
		return nullptr;
	}
};

class ChicagoPizzaStore : public PizzaStore {
protected:
	std::unique_ptr<Pizza> CreatePizza(const std::string& type) override {
		if (type == "cheese") {
			return std::make_unique<ChicagoStyleCheesePizza>();
		} else if (type == "pepperoni") {
			return std::make_unique<ChicagoStylePepperoniPizza>();
		} else if (type == "veggie") {
			return std::make_unique<ChicagoStyleVeggiePizza>();
		}
		return nullptr;
	}
};

// Abstract Factory Pattern (bonus)
// Used when you need to create families of related objects

struct Dough {
	virtual ~Dough() = default;
	virtual std::string GetType() const = 0;
};

struct Sauce {
	virtual ~Sauce() = default;
	virtual std::string GetType() const = 0;
};

struct Cheese {
	virtual ~Cheese() = default;
	virtual std::string GetType() const = 0;
};

// Abstract Factory interface
struct PizzaIngredientFactory {
	virtual ~PizzaIngredientFactory() = default;
	virtual std::unique_ptr<Dough> CreateDough() = 0;
	virtual std::unique_ptr<Sauce> CreateSauce() = 0;
	virtual std::unique_ptr<Cheese> CreateCheese() = 0;
};

// Concrete Ingredient implementations - NY Style
class ThinCrustDough : public Dough {
public:
	std::string GetType() const override {
		return "Thin Crust Dough";
	}
};

class MarinaraSauce : public Sauce {
public:
	std::string GetType() const override {
		return "Marinara Sauce";
	}
};

class ReggianoCheese : public Cheese {
public:
	std::string GetType() const override {
		return "Reggiano Cheese";
	}
};

// Concrete Ingredient implementations - Chicago Style
class ThickCrustDough : public Dough {
public:
	std::string GetType() const override {
		return "Extra Thick Crust Dough";
	}
};

class PlumTomatoSauce : public Sauce {
public:
	std::string GetType() const override {
		return "Plum Tomato Sauce";
	}
};

class MozzarellaCheese : public Cheese {
public:
	std::string GetType() const override {
		return "Shredded Mozzarella";
	}
};

// Concrete Factories - create families of related ingredients
class NYPizzaIngredientFactory : public PizzaIngredientFactory {
public:
	std::unique_ptr<Dough> CreateDough() override {
		return std::make_unique<ThinCrustDough>();
	}

	std::unique_ptr<Sauce> CreateSauce() override {
		return std::make_unique<MarinaraSauce>();
	}

	std::unique_ptr<Cheese> CreateCheese() override {
		return std::make_unique<ReggianoCheese>();
	}
};

class ChicagoPizzaIngredientFactory : public PizzaIngredientFactory {
public:
	std::unique_ptr<Dough> CreateDough() override {
		return std::make_unique<ThickCrustDough>();
	}

	std::unique_ptr<Sauce> CreateSauce() override {
		return std::make_unique<PlumTomatoSauce>();
	}

	std::unique_ptr<Cheese> CreateCheese() override {
		return std::make_unique<MozzarellaCheese>();
	}
};

// Pizza that uses ingredient factory
class CheesePizza : public Pizza {
private:
	std::unique_ptr<Dough> dough_;
	std::unique_ptr<Sauce> sauce_;
	std::unique_ptr<Cheese> cheese_;

public:
	explicit CheesePizza(PizzaIngredientFactory& ingredientFactory) {
		name = "Cheese Pizza";
		dough_ = ingredientFactory.CreateDough();
		sauce_ = ingredientFactory.CreateSauce();
		cheese_ = ingredientFactory.CreateCheese();
	}

	void Prepare() override {
		std::cout << "Preparing " << name << "\n";
		std::cout << "Tossing dough: " << dough_->GetType() << "\n";
		std::cout << "Adding sauce: " << sauce_->GetType() << "\n";
		std::cout << "Adding cheese: " << cheese_->GetType() << "\n";
	}
};

class PepperoniPizza : public Pizza {
private:
	std::unique_ptr<Dough> dough_;
	std::unique_ptr<Sauce> sauce_;
	std::unique_ptr<Cheese> cheese_;

public:
	explicit PepperoniPizza(PizzaIngredientFactory& ingredientFactory) {
		name = "Pepperoni Pizza";
		dough_ = ingredientFactory.CreateDough();
		sauce_ = ingredientFactory.CreateSauce();
		cheese_ = ingredientFactory.CreateCheese();
	}

	void Prepare() override {
		std::cout << "Preparing " << name << "\n";
		std::cout << "Tossing dough: " << dough_->GetType() << "\n";
		std::cout << "Adding sauce: " << sauce_->GetType() << "\n";
		std::cout << "Adding cheese: " << cheese_->GetType() << "\n";
		std::cout << "Adding pepperoni\n";
	}
};

// Usage example
inline void FactoryPatternDemo() {
	NYPizzaStore nyStore;
	ChicagoPizzaStore chicagoStore;

	auto pizza1 = nyStore.OrderPizza("cheese");
	std::cout << "Ethan ordered a " << pizza1->GetName() << "\n\n";

	auto pizza2 = chicagoStore.OrderPizza("cheese");
	std::cout << "Joel ordered a " << pizza2->GetName() << "\n\n";
}

// Abstract Factory Demo
inline void AbstractFactoryDemo() {
	std::cout << "=== Abstract Factory Pattern Demo ===\n\n";

	// Create NY ingredient factory
	NYPizzaIngredientFactory nyFactory;
	auto nyCheesePizza = std::make_unique<CheesePizza>(nyFactory);
	nyCheesePizza->Prepare();
	std::cout << "\n";

	// Create Chicago ingredient factory
	ChicagoPizzaIngredientFactory chicagoFactory;
	auto chicagoPepperoniPizza = std::make_unique<PepperoniPizza>(chicagoFactory);
	chicagoPepperoniPizza->Prepare();
	std::cout << "\n";

	// Key benefit: Guaranteed ingredient compatibility
	// NY Pizza always gets NY-style ingredients
	// Chicago Pizza always gets Chicago-style ingredients
}

}  // namespace factory_pattern
