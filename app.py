import os
import traceback
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from scraper import run_scraper_to_memory

app = Flask(__name__)

INPUT_FILE = "data/input.xlsx"
OUTPUT_FILE = "downloads/Topps_Reviews_Output.xlsx"

os.makedirs("data", exist_ok=True)
os.makedirs("downloads", exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/process", methods=["POST"])
def process():
    try:
        data = request.json or {}
        start_date = data.get("startDate") or None
        end_date = data.get("endDate") or None
        rating_filter = data.get("ratingFilter", "all")
        threshold_val = data.get("thresholdRating")
        custom_ratings = data.get("customRatings", [])

        threshold = int(threshold_val) if (rating_filter == "threshold" and threshold_val) else None
        selected_ratings = [int(r) for r in custom_ratings] if (rating_filter == "custom" and custom_ratings) else []

        if not os.path.exists(INPUT_FILE):
            return jsonify({"error": f"Input workbook 'data/input.xlsx' not found."}), 400

        # Run scraper loop 
        success, result_data = run_scraper_to_memory(
            input_path=INPUT_FILE,
            start_date_str=start_date,
            end_date_str=end_date,
            rating_type=rating_filter,
            threshold=threshold,
            selected_ratings=selected_ratings
        )

        if not success:
            return jsonify({"error": result_data}), 500

        # Also save to an Excel file automatically in the background
        if result_data:
            export_df = pd.DataFrame(result_data)
            # Remove numeric rating column used for charts before saving
            if "rating_num" in export_df.columns:
                export_df = export_df.drop(columns=["rating_num"])
            export_df.to_excel(OUTPUT_FILE, index=False)

        return jsonify({"success": True, "reviews": result_data})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Backend Error: {str(e)}"}), 500

@app.route("/download-excel")
def download_excel():
    if os.path.exists(OUTPUT_FILE):
        return send_file(OUTPUT_FILE, as_attachment=True)
    return "File not found", 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )